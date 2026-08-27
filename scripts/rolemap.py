"""rolemap: D3 岗位目录映射与等级推断。

用法：
    uv run scripts/rolemap.py run          # 规则匹配 + LLM 候选 -> jd-role-map.jsonl
    uv run scripts/rolemap.py label        # 生成人工标注包 CSV（review-labels.csv）

映射：JD 职位名 -> Excel 46 标准岗位。规则精确/别名匹配优先（零成本零幻觉），
未命中交 LLM 语义候选（带置信度和理由），均写入映射档案。
等级：L1-L4 由确定性规则从经验要求与职位名推断（记录依据字段），
     冲突或缺失为 UNKNOWN，进人工标注。
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.infra.llm.promptspec import load_prompt  # noqa: E402
from backend.infra.llm.provider import build_provider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
POSITIONS = ROOT / "data" / "processed" / "capability-matrix" / "positions.jsonl"
OUT = ROOT / "data" / "processed" / "jd-opencli" / "jd-role-map.jsonl"
LABELS = ROOT / "data" / "processed" / "jd-opencli" / "review-labels.csv"
MAX_RETRIES = 2

# 职位名别名（市场叫法 -> Excel 标准名），人工先验
TITLE_ALIASES: dict[str, str] = {
    "大模型": "大模型算法工程师",
    "LLM": "大模型算法工程师",
    "AIGC": "AI创意策略师",
    "NLP": "NLP/多模态研究员",
    "Agent": "AI Agent开发工程师",
    "智能体": "AI Agent开发工程师",
    "机器学习": "NLP/多模态研究员",
    "深度学习": "NLP/多模态研究员",
    "计算机视觉": "计算机视觉工程师",
    "CV": "计算机视觉工程师",
    "MLOps": "AI模型部署工程师(MLOps)",
    "数据标注": "数据标注/AI数据专员",
    "大数据": "大数据工程师",
    "数据开发": "大数据工程师",
    "数仓": "大数据工程师",
    "云计算": "云计算/AI基础设施工程师",
    "运维开发": "数据中心运维工程师",
    "DevOps": "数据中心运维工程师",
    "嵌入式": "嵌入式AI工程师",
    "物联网": "物联网(IoT)架构师",
    "IoT": "物联网(IoT)架构师",
    "产品经理": "AI产品经理",
    "Prompt": "Prompt工程师",
}

LEVEL_BY_EXPERIENCE = [
    (("在校", "应届", "实习", "1年以内", "经验不限"), "L1", "经验要求"),
    (("1-3年", "1-3", "一年以上"), "L2", "经验要求"),
    (("3-5年", "3-5", "5-10年"), "L3", "经验要求"),
    (("10年以上",), "L4", "经验要求"),
]
LEVEL_BY_TITLE = [
    (("首席", "专家", "负责人", "总监", "CTO", "架构师"), "L4", "职位名"),
    (("高级", "资深", "Senior"), "L3", "职位名"),
    (("助理", "初级", "实习", "Junior"), "L1", "职位名"),
]


def match_by_rule(title: str, positions: list[dict]) -> tuple[str | None, float, str]:
    """规则匹配：标准名包含 > 别名包含。返回 (position_id, confidence, method)。"""
    norm = title.replace(" ", "").replace("（", "(")
    for p in positions:
        base = p["name"].replace("（", "(").split("(")[0]
        if base and base in norm:
            return p["position_id"], 1.0, "exact"
    for alias, target in TITLE_ALIASES.items():
        if alias in norm:
            for p in positions:
                if p["name"] == target:
                    return p["position_id"], 0.7, "alias"
    return None, 0.0, ""


def infer_level(title: str, work_year: str) -> tuple[str, str]:
    """等级推断：职位名关键词优先（更具体），其次经验要求。返回 (level, basis)。"""
    norm = title.replace(" ", "")
    for keys, level, basis in LEVEL_BY_TITLE:
        if any(k in norm for k in keys):
            return level, f"{basis}:{next(k for k in keys if k in norm)}"
    wy = work_year or ""
    for keys, level, basis in LEVEL_BY_EXPERIENCE:
        if any(k in wy for k in keys):
            return level, f"{basis}:{wy or '经验不限'}"
    return "UNKNOWN", "无信号"


def _catalog(positions: list[dict]) -> str:
    return "\n".join(f"{p['position_id']} {p['name']}（{p['group']}）" for p in positions)


def _parse(raw: str, jd_id: str) -> dict:
    from backend.jobs.models import RoleMatch

    t = raw.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError("输出必须是 JSON 对象")
    data.pop("jd_id", None)
    return RoleMatch.model_validate({**data, "jd_id": jd_id}).model_dump()


async def cmd_run() -> dict:
    settings = LLMSettings()
    run = RunContext("rolemap", {"cmd": "run"})
    spec = load_prompt("role-map")
    provider = build_provider(settings)
    positions = [json.loads(x) for x in POSITIONS.open(encoding="utf-8")]
    rows = [
        r for r in (json.loads(x) for x in PARSED.open(encoding="utf-8")) if r.get("is_ai_role")
    ]

    done: set[str] = set()
    if OUT.is_file():
        for line in OUT.open(encoding="utf-8"):
            done.add(json.loads(line).get("jd_id"))
    todo = [r for r in rows if r["jd_id"] not in done]

    sem = asyncio.Semaphore(15)
    fh = OUT.open("a", encoding="utf-8")
    llm_hits = misses = 0

    async def one(r: dict) -> None:
        nonlocal llm_hits, misses
        title = r["title"]
        pid, conf, method = match_by_rule(title, positions)
        level, basis = infer_level(title, r.get("work_year") or "")
        if pid:
            rec = {
                "jd_id": r["jd_id"],
                "platform": r["platform"],
                "title": title,
                "position_id": pid,
                "confidence": conf,
                "method": method,
                "level": level,
                "level_basis": basis,
                "publish_date": r.get("publish_date"),
            }
        else:
            # LLM 语义候选
            message = (
                f"jd_id: {r['jd_id']}\n职位名: {title}\n经验要求: {r.get('work_year') or '未知'}\n"
                f"职责摘要: {'; '.join(r.get('responsibilities') or [])[:300]}\n\n"
                f"标准岗位清单:\n{_catalog(positions)}\n\n任务: {spec.task}。只输出 JSON。"
            )
            last_err = "unknown"
            cand = None
            async with sem:
                for attempt in range(1 + MAX_RETRIES):
                    user = (
                        message
                        if attempt == 0
                        else f"{message}\n\n上次失败: {last_err}\n重新输出。"
                    )
                    try:
                        raw = await provider.complete(
                            system=spec.system,
                            user=user,
                            max_tokens=int(spec.limits.get("max_tokens", 400)),
                            timeout=float(spec.limits.get("timeout_seconds", 60)),
                        )
                        cand = _parse(raw, r["jd_id"])
                        break
                    except Exception as exc:  # noqa: BLE001
                        last_err = f"{type(exc).__name__}: {exc}"[:150]
            pid = (cand or {}).get("position_id") if (cand or {}).get("is_match") else None
            if pid:
                llm_hits += 1
                rec = {
                    "jd_id": r["jd_id"],
                    "platform": r["platform"],
                    "title": title,
                    "position_id": pid,
                    "confidence": (cand or {}).get("confidence", 0),
                    "method": "llm",
                    "level": level,
                    "level_basis": basis,
                    "publish_date": r.get("publish_date"),
                    "reason": (cand or {}).get("reason", ""),
                }
            else:
                misses += 1
                rec = {
                    "jd_id": r["jd_id"],
                    "platform": r["platform"],
                    "title": title,
                    "position_id": None,
                    "confidence": 0,
                    "method": "unmatched",
                    "level": level,
                    "level_basis": basis,
                    "publish_date": r.get("publish_date"),
                    "error": last_err if not cand else "llm_no_match",
                }
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    try:
        await asyncio.gather(*(one(r) for r in todo))
    finally:
        fh.close()
    all_recs = [json.loads(x) for x in OUT.open(encoding="utf-8")] if OUT.is_file() else []
    from collections import Counter

    by_method = Counter(r["method"] for r in all_recs)
    metrics = {
        "targets": len(rows),
        "todo": len(todo),
        "by_method": dict(by_method),
        "levels": dict(Counter(r["level"] for r in all_recs)),
        "prompt_version": spec.version,
        "model_version": provider.model_version,
        **provider.usage.as_dict(),
    }
    run.finish({k: v for k, v in metrics.items() if not isinstance(v, dict)})
    return metrics


def cmd_label() -> dict:
    """生成人工标注包：映射与等级双确认列。"""
    run = RunContext("rolemap", {"cmd": "label"})
    recs = [json.loads(x) for x in OUT.open(encoding="utf-8")]
    positions = {
        p["position_id"]: p["name"]
        for p in (json.loads(x) for x in POSITIONS.open(encoding="utf-8"))
    }
    LABELS.parent.mkdir(parents=True, exist_ok=True)
    with LABELS.open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            [
                "jd_id",
                "职位名",
                "系统岗位",
                "系统置信度",
                "系统等级",
                "等级依据",
                "映射正确?(对/错)",
                "修正岗位",
                "等级正确?(对/错)",
                "修正等级",
                "备注",
            ]
        )
        for r in recs:
            w.writerow(
                [
                    r["jd_id"],
                    r["title"],
                    positions.get(r.get("position_id") or "", ""),
                    r.get("confidence", ""),
                    r["level"],
                    r.get("level_basis", ""),
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
    n = len(recs)
    run.finish({"rows": n})
    return {"rows": n, "file": str(LABELS)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rolemap")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("label")
    args = parser.parse_args(argv)
    import asyncio

    result = asyncio.run(cmd_run()) if args.cmd == "run" else cmd_label()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
