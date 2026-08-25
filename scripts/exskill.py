"""exskill: Excel 岗位职责简介的结构化抽取与归一（专家基线画像）。

用法：
    uv run scripts/exskill.py run            # 46 岗位 LLM 抽取 -> position-skills.jsonl
    uv run scripts/exskill.py keywords       # 46 岗位名清洗成搜索关键词表 -> excel-keywords.txt

run：LLM 逐岗位抽取 职责/要求/技能原词（prompts/position-skill.yml），
     再用 SKILLS 词典确定性归一，输出可与 JD 信号同词表对比的岗位画像。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.infra.llm.promptspec import load_prompt  # noqa: E402
from backend.infra.llm.provider import build_provider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402
from backend.skills.models import PositionSkill  # noqa: E402
from backend.skills.resolver import load_resolver  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
POSITIONS = ROOT / "data" / "processed" / "capability-matrix" / "positions.jsonl"
OUT = ROOT / "data" / "processed" / "capability-matrix" / "position-skills.jsonl"
KEYWORDS_OUT = ROOT / "data" / "processed" / "jd-opencli" / "excel-keywords.txt"
MAX_RETRIES = 2


def _parse(raw: str, position_id: str) -> PositionSkill:
    """解析模型输出；接受扁平形式或 {position: {...}} 包装形式，position_id 由输入回填。"""
    from backend.skills.models import PositionSkill

    t = raw.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    data = json.loads(t)
    if not isinstance(data, dict):
        raise ValueError("输出必须是 JSON 对象")
    if "position" in data and isinstance(data["position"], dict):
        data = data["position"]
    if "responsibilities" not in data and "requirements" not in data:
        raise ValueError("输出缺少 responsibilities/requirements")
    data.pop("position_id", None)
    return PositionSkill.model_validate({**data, "position_id": position_id})


async def cmd_run() -> dict:

    settings = LLMSettings()
    run = RunContext("exskill", {"cmd": "run"})
    spec = load_prompt("position-skill")
    provider = build_provider(settings)
    resolver = load_resolver()
    positions = [json.loads(x) for x in POSITIONS.open(encoding="utf-8")]

    done: set[str] = set()
    if OUT.is_file():
        for line in OUT.open(encoding="utf-8"):
            done.add(json.loads(line).get("position_id"))
    todo = [p for p in positions if p["position_id"] not in done]

    sem = asyncio.Semaphore(4)
    fh = OUT.open("a", encoding="utf-8")
    results, quarantined = [], []

    async def one(pos: dict) -> None:
        message = (
            f"岗位 ID: {pos['position_id']}\n"
            f"岗位名称: {pos['name']}\n\n"
            f"职责简介全文:\n{pos.get('summary') or ''}"
        )
        last_err = "unknown"
        async with sem:
            for attempt in range(1 + MAX_RETRIES):
                user = (
                    message
                    if attempt == 0
                    else f"{message}\n\n上次失败: {last_err}\n重新输出 JSON。"
                )
                try:
                    raw = await provider.complete(
                        system=spec.system,
                        user=user,
                        max_tokens=int(spec.limits.get("max_tokens", 1500)),
                        timeout=float(spec.limits.get("timeout_seconds", 120)),
                    )
                    parsed = _parse(raw, pos["position_id"])
                except Exception as exc:  # noqa: BLE001 - 校验/API 异常计入重试
                    last_err = f"{type(exc).__name__}: {exc}"[:200]
                    continue
                mentions = parsed.skill_mentions
                resolved = []
                for m in mentions:
                    hit = resolver.resolve(m)
                    if hit.skill_id:
                        resolved.append(
                            {"mention": m, "skill_id": hit.skill_id, "point_id": hit.point_id}
                        )
                results.append(parsed.model_dump())
                fh.write(
                    json.dumps(
                        {
                            **parsed.model_dump(),
                            "name": pos["name"],
                            "group": pos["group"],
                            "resolved": resolved,
                            "unresolved": [m for m in mentions if not resolver.resolve(m).skill_id],
                            "rule_version": resolver.version,
                            "prompt_version": spec.version,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                fh.flush()
                return
        quarantined.append({"position_id": pos["position_id"], "error": last_err})

    try:
        await asyncio.gather(*(one(p) for p in todo))
    finally:
        fh.close()
    metrics = {
        "positions": len(todo),
        "extracted": len(results),
        "quarantined": len(quarantined),
        "prompt_version": spec.version,
        "model_version": provider.model_version,
        **provider.usage.as_dict(),
    }
    run.finish(metrics)
    return metrics


def cmd_keywords() -> dict:
    """46 岗位名清洗为搜索关键词：去括号、拆斜杠、过滤明显无搜索量的岗位。"""
    run = RunContext("exskill", {"cmd": "keywords"})
    positions = [json.loads(x) for x in POSITIONS.open(encoding="utf-8")]
    skip = {"首席人工智能官"}  # 高管岗，平台无对应在招
    kws: list[str] = []
    for p in positions:
        name = p["name"]
        if name in skip:
            continue
        base = re.sub(r"[（(][^）)]*[）)]", "", name).strip()
        parts = [x.strip() for x in base.split("/") if x.strip()]
        for part in parts:
            if 2 <= len(part) <= 15 and part not in kws:
                kws.append(part)
    KEYWORDS_OUT.parent.mkdir(parents=True, exist_ok=True)
    KEYWORDS_OUT.write_text("\n".join(kws) + "\n", encoding="utf-8")
    run.finish({"keywords": len(kws)})
    return {"keywords": len(kws), "file": str(KEYWORDS_OUT)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="exskill")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    sub.add_parser("keywords")
    args = parser.parse_args(argv)
    result = asyncio.run(cmd_run()) if args.cmd == "run" else cmd_keywords()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
