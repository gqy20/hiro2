"""resolve: D4 技能归一化 CLI。

用法：
    uv run scripts/resolve.py events [--as-of YYYY-MM-DD]   # 全量映射 + 分桶覆盖 + 未命中词单
    uv run scripts/resolve.py dates                          # 用当前语料重算习得别名首见日期

--as_of 非空时，SKILLS-EARNED.yml 中 effective_from > as_of 的别名不参与匹配（防规则泄漏）。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.skills.resolver import EARNED_FILE, load_resolver, parse_day  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "wechat-mp"


def _event_day(e: dict) -> str | None:
    return (e.get("published_at") or e.get("published_date") or "")[:10] or None


def cmd_events(as_of: date | None) -> dict:
    run = RunContext("resolve", {"cmd": "events", "as_of": str(as_of) if as_of else None})
    resolver = load_resolver(as_of=as_of)
    events = [json.loads(x) for x in (PROCESSED / "events.jsonl").open(encoding="utf-8")]

    mappings = []
    word_total: Counter[str] = Counter()
    word_hit: Counter[str] = Counter()
    unmatched_samples: dict[str, dict] = {}

    for e in events:
        for mention in e.get("skill_mentions", []):
            r = resolver.resolve(mention)
            word_total[mention] += 1
            if r.skill_id:
                word_hit[mention] += 1
            else:
                day = _event_day(e)
                prev = unmatched_samples.get(mention)
                # 保留最早出现的事件作为样例上下文
                if prev is None or (day or "9999") < (prev["first_seen"] or "9999"):
                    unmatched_samples[mention] = {
                        "word": mention,
                        "count": 0,
                        "first_seen": day,
                        "sample_event_id": e["event_id"],
                        "sample_title": e["title"],
                        "sample_summary": e["summary"][:200],
                    }
            mappings.append(
                {
                    "event_id": e["event_id"],
                    "item_id": e["item_id"],
                    "mention": mention,
                    "skill_id": r.skill_id,
                    "point_id": r.point_id,
                    "matched_by": r.matched_by,
                    "rule_version": resolver.version,
                }
            )

    for w, sample in unmatched_samples.items():
        sample["count"] = word_total[w]

    suffix = "-asof" if as_of else ""
    with (PROCESSED / f"skill-mappings{suffix}.jsonl").open("w", encoding="utf-8") as fh:
        for m in mappings:
            fh.write(json.dumps(m, ensure_ascii=False) + "\n")
    unmatched_sorted = sorted(unmatched_samples.values(), key=lambda x: -x["count"])
    with (PROCESSED / f"unmatched-words{suffix}.jsonl").open("w", encoding="utf-8") as fh:
        for row in unmatched_sorted:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")

    def bucket(lo: int, hi: int) -> dict[str, int]:
        words = [w for w, n in word_total.items() if lo <= n <= hi]
        tot = sum(word_total[w] for w in words)
        hit = sum(word_hit[w] for w in words)
        return {"words": len(words), "mentions": tot, "matched": hit}

    total = sum(word_total.values())
    matched = sum(word_hit.values())
    metrics = {
        "as_of": str(as_of) if as_of else None,
        "mentions": total,
        "matched": matched,
        "coverage_weighted": round(matched / total, 3) if total else 0.0,
        "coverage_midhigh_ge2": bucket(2, 10**9),
        "coverage_high_ge5": bucket(5, 10**9),
        "coverage_tail_1": bucket(1, 1),
        "unmatched_distinct": len(unmatched_sorted),
        "rule_version": resolver.version,
    }
    (PROCESSED / f"skill-resolve-stats{suffix}.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    run.log("resolve", "finished", "succeeded", count={"mentions": total, "matched": matched})
    run.finish({k: v for k, v in metrics.items() if not isinstance(v, dict)})
    return metrics


def cmd_dates() -> dict:
    """用当前语料重算 SKILLS-EARNED.yml 的 effective_from（首见日期）。"""
    run = RunContext("resolve", {"cmd": "dates"})
    if not EARNED_FILE.is_file():
        run.log("dates", "earned_missing", "failed", detail=str(EARNED_FILE))
        run.finish({}, "FAILED")
        raise SystemExit(2)
    import yaml

    data = yaml.safe_load(EARNED_FILE.read_text(encoding="utf-8"))
    events = [json.loads(x) for x in (PROCESSED / "events.jsonl").open(encoding="utf-8")]
    first: dict[str, tuple[str, str]] = {}  # mention -> (day, event_id)
    for e in sorted(events, key=lambda ev: _event_day(ev) or ""):
        day = _event_day(e)
        if not day:
            continue
        for m in e.get("skill_mentions", []):
            if m not in first:
                first[m] = (day, e["event_id"])
    updated = 0
    for raw in data.get("aliases", []):
        hit = first.get(raw["mention"])
        if hit and hit[0] != raw.get("effective_from"):
            raw["effective_from"] = hit[0]
            raw["sample_event_id"] = hit[1]
            updated += 1
    EARNED_FILE.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    run.log("dates", "updated", "succeeded", count=updated)
    run.finish({"aliases": len(data.get("aliases", [])), "updated": updated})
    return {"aliases": len(data.get("aliases", [])), "updated": updated}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="resolve")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_events = sub.add_parser("events")
    p_events.add_argument("--as-of", type=str, default=None)
    sub.add_parser("dates")
    args = parser.parse_args(argv)

    if args.cmd == "events":
        as_of = parse_day(args.as_of) if args.as_of else None
        if args.as_of and as_of is None:
            raise SystemExit(f"--as-of 非法: {args.as_of}")
        metrics = cmd_events(as_of)
    else:
        metrics = cmd_dates()
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
