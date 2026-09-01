"""shootout: 岗位映射方案对比——10 条固定锚定案例，小样本选定方案再扩大。

纪律（本轮迭代的教训）：先 10 条小样本对比，赢家才谈扩大；gold 只用已锚定
（ai-cross-review corrected_payload）的 case，不再双向漂移。

四个候选方案（基于业界调研）：
  s1  任务分解两段式（TGRE 精神）：先归纳核心职责一句话 + 判"是否属46岗目录"，
      再选岗。针对 None 类错误（管理/商务/目录外被硬塞岗）。
  s2  置信度门控（ACM 式）：第一轮快速判 + 自报置信度；低置信（<0.7）的第二轮
      带岗位职责对照重判。针对边界 case。
  s3  人工判例 few-shot：prompt 内嵌 8 个精选判例（覆盖多模态细分/产品优先/
      Manager 排除/FDE 新岗等模式），零检索。
  s4  s1 + s3 组合（分解 + 判例）。

用法：uv run scripts/shootout.py [s1|s2|s3|s4|all]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "evaluation" / "samples"
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"

# 10 条固定锚定案例（gold 来自 ai-cross-review corrected_payload）
CASES: dict[int, str | None] = {
    63: None,
    53: None,
    72: None,
    85: None,  # None 类（管理/测试/全栈/售前）
    12: "pos_04",
    41: "pos_04",
    79: "pos_04",  # 多模态细分
    16: "pos_04",
    45: "pos_05",  # 方向细分
    77: "pos_18",  # 边界（AI合规）
}

# s3 人工精选判例（与测试集不重叠；模式覆盖：细分/排除/方向）
SHOTS = """判例（已验证归属，判断时对照职责语义）：
- "多模态算法实习生-电商业务（平台治理）" 职责=多模态预训练对齐 -> pos_04（多模态研究，非pos_01）
- "高级产品经理（大模型数据管理平台）" 职责=交互设计/平台Agent化 -> pos_06（产品岗优先于技术词）
- "Manager of Applied AI Architecture" 职责=战略路线图/ROI评估 -> unmatched（管理岗不属技术目录）
- "AI测试开发工程师" 职责=质量保障/交付验收 -> unmatched（测试岗不属46岗目录）
- "算法工程专家（模型推理平台）" 职责=推理调度/量化剪枝 -> pos_05（推理服务，非pos_01）
- "Staff Machine Learning Engineer, Visual" 职责=视觉编码器/VLM/扩散模型 -> pos_04（多模态研究）
- "高级应用解决方案经理-信息安全" 职责=安全合规方案设计 -> pos_18（AI合规）
- "算法工程师-搜索" 职责=NLP/召回排序 -> pos_04（NLP方向细分）"""

CATALOG = None  # 延迟加载


def _catalog() -> str:
    global CATALOG
    if CATALOG is None:
        _pos_path = ROOT / "data" / "processed" / "capability-matrix" / "positions.jsonl"
        _positions = [json.loads(line) for line in _pos_path.open()]
        CATALOG = "\n".join(f"{p['position_id']} {p.get('group')}/{p['name']}" for p in _positions)
    return CATALOG


def _jd_block(jd: dict) -> str:
    resp = "\n".join(f"- {x[:60]}" for x in (jd.get("responsibilities") or [])[:5])
    skills = ", ".join((jd.get("skill_mentions") or [])[:10])
    return f"职责:\n{resp}\n技能: {skills}"


S1_SYSTEM = """你是岗位目录映射器，分两步作答：
步骤1：用一句话归纳该 JD 的核心工作内容（"该岗位实际在做___"）。
步骤2：基于归纳判断——核心工作是否属于 46 个 AI 技术岗位之一？
- 不属于（管理/商务/售前/测试/传统前后端等） -> is_match=false
- 属于 -> 从目录选最贴合岗位（职责语义优先于职位名字面；细分方向看职责：
  多模态/VLM/扩散研究属 pos_04，推理服务/部署属 pos_05，Agent框架属 pos_02，
  LLM预训练微调属 pos_01，合规治理属 pos_18）
只输出 JSON：{"jd_id":"...","core_work":"一句话","is_match":true,
"position_id":"pos_XX","confidence":0.9,"reason":"..."}"""

S3_SYSTEM = """你是岗位目录映射器。先对照下方判例找相似模式，再按职责语义判断归属。
判例模式优先：管理/测试/售前/纯前后端 -> is_match=false；细分方向按职责判
（判例里的 pos_04/pos_05/pos_18 等先例）。
{shots}

只输出 JSON：{"jd_id":"...","is_match":true,"position_id":"pos_XX",
"confidence":0.9,"reason":"..."}"""


def _parse_pred(raw: str, jd_id: str) -> str | None | dict:
    t = raw.strip()
    if t.startswith("```"):
        nl = t.find("\n")
        t = t[nl + 1 :] if nl != -1 else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    try:
        d = json.loads(t.strip())
        return (
            (d.get("position_id") if d.get("is_match") else None)
            if d.get("jd_id") == jd_id
            else "FORMAT_ERROR"
        )
    except Exception:
        return "PARSE_ERROR"


async def run_scheme(scheme: str, porter) -> dict:
    import csv

    rows = list(csv.DictReader((SAMPLES / "role-mapping.csv").open(encoding="utf-8-sig")))
    parsed = {json.loads(line)["jd_id"]: json.loads(line) for line in PARSED.open(encoding="utf-8")}
    run = RunContext("shootout", {"scheme": scheme, "n": len(CASES)})
    results = []
    for idx, gold in CASES.items():
        row = rows[idx]
        jd = parsed.get(row["jd_id"], {})
        user = (
            f"jd_id: {row['jd_id']}\n职位名: {row['职位名']}\n{_jd_block(jd)}"
            f"\n\n标准岗位目录:\n{_catalog()}"
        )
        if scheme == "s1":
            system = S1_SYSTEM
        elif scheme == "s3":
            system = S3_SYSTEM.replace("{shots}", SHOTS)
        elif scheme == "s4":
            system = S1_SYSTEM + "\n\n" + SHOTS
        elif scheme == "s2":
            # 置信度门控：第一轮快速判，低置信二轮重判（带自我对照提示）
            system = S1_SYSTEM
        else:
            raise ValueError(scheme)

        async def call(sysp: str, usr: str) -> str:
            return await porter.complete(system=sysp, user=usr, max_tokens=1500, timeout=240)

        raw = await call(system, user)
        pred = _parse_pred(raw, row["jd_id"])
        conf = 0.0
        if isinstance(pred, (str, None.__class__)) and pred not in ("PARSE_ERROR", "FORMAT_ERROR"):
            try:
                d = json.loads(
                    raw.strip()
                    .removeprefix("```json")
                    .removeprefix("```")
                    .removesuffix("```")
                    .strip()
                )
                conf = float(d.get("confidence", 0))
            except Exception:
                pass
        if scheme == "s2" and conf < 0.7:
            # 二轮：强调对照目录职责与"不属于目录就 unmatched"
            retry = await call(
                system + "\n\n注意：你上一轮置信度不足。重新审视职责——若核心工作不属46岗目录"
                "（管理/测试/售前/传统前后端），必须 is_match=false；若属细分方向，按职责选岗。",
                user,
            )
            new_pred = _parse_pred(retry, row["jd_id"])
            if new_pred not in ("PARSE_ERROR", "FORMAT_ERROR"):
                pred = new_pred
        ok = pred == gold
        results.append(
            {"idx": idx, "title": row["职位名"][:30], "pred": pred, "gold": gold, "ok": ok}
        )
        mark = "✓" if ok else "✗"
        print(f"  [{idx:03d}] {mark} pred={str(pred):8} gold={str(gold):8} {row['职位名'][:30]}")

    acc = sum(1 for r in results if r["ok"]) / len(results)
    summary = {
        "scheme": scheme,
        "accuracy": round(acc, 2),
        "correct": sum(1 for r in results if r["ok"]),
        "n": len(results),
        "results": results,
    }
    (run.dir / "shootout.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    run.finish({"accuracy": acc})
    print(f"{scheme}: {sum(1 for r in results if r['ok'])}/{len(results)} = {acc:.0%}\n")
    return summary


async def main_async(schemes: list[str]) -> None:
    from backend.infra.llm.provider import AnthropicProvider
    from backend.infra.llm.settings import LLMSettings

    porter = AnthropicProvider(LLMSettings())
    for s in schemes:
        await run_scheme(s, porter)
    print(f"总 token: {porter.usage.as_dict()}")


def _full_cases() -> dict[int, str | None]:
    """全部锚定 gold case（ai-cross-review corrected_payload 或 ACCEPT 锚定）。"""
    import csv

    rows = list(csv.DictReader((SAMPLES / "role-mapping.csv").open(encoding="utf-8-sig")))
    latest: dict[str, dict] = {}
    ann = ROOT / "evaluation" / "annotations.jsonl"
    for line in ann.open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("dataset_version") == "eval-v3-20260828":
            latest[r["task_id"]] = r
    repaired = {
        json.loads(line)["jd_id"]: json.loads(line)
        for line in (ROOT / "data/processed/jd-opencli/jd-role-map-repaired.jsonl").open()
    }
    cases: dict[int, str | None] = {}
    for i, row in enumerate(rows):
        tid = f"task-role_level-{i:03d}"
        a = latest.get(tid)
        if a is None or a["decision"] == "UNKNOWN":
            continue
        anchored = (a.get("corrected_payload") or {}).get("position_id")
        if anchored is not None:
            cases[i] = anchored
        elif a["decision"] == "ACCEPT":
            cases[i] = repaired.get(row["jd_id"], {}).get("position_id")
        else:
            cases[i] = None
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="shootout")
    parser.add_argument("scheme", choices=("s1", "s2", "s3", "s4", "all"))
    parser.add_argument("--full", action="store_true", help="全部锚定 case（非仅 10 条固定集）")
    args = parser.parse_args(argv)
    global CASES
    if args.full:
        CASES = _full_cases()
        print(f"全量模式：{len(CASES)} 条锚定 case")
    schemes = ["s1", "s2", "s3", "s4"] if args.scheme == "all" else [args.scheme]
    asyncio.run(main_async(schemes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
