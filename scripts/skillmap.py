"""skillmap: 离线技能归一任务（词典生产，非数据管线）。

用法：
    uv run scripts/skillmap.py batch [--min-count 2] [--limit N]

读取 unmatched-words.jsonl，把候选词 + 上下文发给 LLM 归派，
输出归派候选（data/processed/wechat-mp/alias-candidates.jsonl），
人工确认后合入 data/SKILLS-EARNED.yml。运行时数据归一不受此影响（永远是查表）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.infra.llm.promptspec import load_prompt  # noqa: E402
from backend.infra.llm.provider import build_provider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402
from backend.skills.models import SkillAliasCandidate  # noqa: E402
from backend.skills.resolver import load_resolver  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "wechat-mp"
CONCURRENCY = 5
MAX_RETRIES = 2


def _parse(raw: str) -> SkillAliasCandidate:
    import json as jsonlib

    t = raw.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1]
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    data = jsonlib.loads(t)
    if not isinstance(data, dict):
        raise ValueError("输出必须是 JSON 对象")
    return SkillAliasCandidate.model_validate(data)


def _user_message(spec, word: dict, catalog: str) -> str:
    return (
        f"候选词: {word['word']}\n"
        f"出现次数: {word['count']}\n"
        f"首见: {word.get('first_seen')}\n"
        f"上下文标题: {word.get('sample_title', '')}\n"
        f"上下文摘要: {word.get('sample_summary', '')}\n\n"
        f"能力域清单:\n{catalog}\n\n"
        f"任务: {spec.task}。只输出符合 schema 的 JSON 对象。"
    )


def _catalog(resolver) -> str:
    lines = []
    for e in resolver.entries:
        points = "、".join(p[0] for p in e.points) or "无"
        lines.append(f"{e.capability_id} {e.name}（技能点: {points}）")
    return "\n".join(lines)


async def cmd_batch(min_count: int, limit: int | None) -> dict:
    settings = LLMSettings()
    run = RunContext("skillmap", {"cmd": "batch", "min_count": min_count})
    spec = load_prompt("skill-alias")
    provider = build_provider(settings)
    resolver = load_resolver()
    catalog = _catalog(resolver)
    max_tokens = int(spec.limits.get("max_tokens", 300))
    timeout = float(spec.limits.get("timeout_seconds", 60))

    words = [
        json.loads(x)
        for x in (PROCESSED / "unmatched-words.jsonl").open(encoding="utf-8")
        if json.loads(x)["count"] >= min_count
    ]
    if limit:
        words = words[:limit]

    sem = asyncio.Semaphore(CONCURRENCY)
    candidates: list[dict] = []
    quarantined: list[dict] = []

    async def one(word: dict) -> None:
        message = _user_message(spec, word, catalog)
        last_error = "unknown"
        for attempt in range(1 + MAX_RETRIES):
            user = (
                message if attempt == 0 else f"{message}\n\n上次失败: {last_error}\n重新输出 JSON。"
            )
            try:
                async with sem:
                    raw = await provider.complete(
                        system=spec.system, user=user, max_tokens=max_tokens, timeout=timeout
                    )
                cand = _parse(raw)
            except Exception as exc:  # noqa: BLE001 - 网关/校验异常计入重试
                last_error = f"{type(exc).__name__}: {exc}"[:200]
                continue
            if cand.word != word["word"]:
                last_error = f"word 不匹配: {cand.word}"
                continue
            candidates.append(
                {
                    **cand.model_dump(),
                    "first_seen": word.get("first_seen"),
                    "count": word["count"],
                }
            )
            return
        quarantined.append({"word": word["word"], "error": last_error})

    await asyncio.gather(*(one(w) for w in words))

    out = PROCESSED / "alias-candidates.jsonl"
    with out.open("a", encoding="utf-8") as fh:
        for c in sorted(candidates, key=lambda x: -x["count"]):
            fh.write(json.dumps(c, ensure_ascii=False) + "\n")

    skill_yes = sum(1 for c in candidates if c["is_skill"] and c["confidence"] >= 0.6)
    metrics = {
        "words": len(words),
        "candidates": len(candidates),
        "skill_confident": skill_yes,
        "rejected_as_noise": sum(1 for c in candidates if not c["is_skill"]),
        "quarantined": len(quarantined),
        "prompt_version": spec.version,
        "model_version": provider.model_version,
        **provider.usage.as_dict(),
    }
    run.log("skillmap", "finished", "succeeded", count=metrics)
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="skillmap")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_batch = sub.add_parser("batch")
    p_batch.add_argument("--min-count", type=int, default=2)
    p_batch.add_argument("--limit", type=int, default=None)
    args = parser.parse_args(argv)
    metrics = asyncio.run(cmd_batch(args.min_count, args.limit))
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
