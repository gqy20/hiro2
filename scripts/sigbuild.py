"""sigbuild: 事件 x 归一映射 -> TrendSignal 落盘（确定性，契约 item 级）。

用法：
    uv run scripts/sigbuild.py build

输入 events.jsonl（仅主记录）+ skill-mappings.jsonl，
输出 data/processed/temporal/signals.jsonl（全量重建）。
confidence 沿用事实分级映射：fact=0.9 / report=0.6 / opinion=0.3。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "processed" / "wechat-mp"
OUT = ROOT / "data" / "processed" / "temporal" / "signals.jsonl"

CONF = {"fact": 0.9, "report": 0.6, "opinion": 0.3}


def cmd_build() -> dict:
    run = RunContext("sigbuild", {"cmd": "build"})
    events = {}
    for line in (SRC / "events.jsonl").open(encoding="utf-8"):
        e = json.loads(line)
        if e.get("duplicate_group_id") and not e.get("is_primary", True):
            continue  # 只消费去重主记录
        events[e["event_id"]] = e

    signals = []
    for line in (SRC / "skill-mappings.jsonl").open(encoding="utf-8"):
        m = json.loads(line)
        ev = events.get(m["event_id"])
        if not ev or not m.get("skill_id"):
            continue
        signals.append(
            {
                "signal_id": f"sig-{m['event_id']}-{m['skill_id']}",
                "item_id": m["item_id"],
                "entity_type": "skill",
                "canonical_skill_id": m["skill_id"],
                "signal_type": "mention",
                "observed_at": ev.get("published_at") or "",
                "evidence_span": ev.get("title", "")[:60],
                "confidence": CONF.get(ev.get("fact_grade", "report"), 0.6),
                "evidence_ids": [f"ev:{m['event_id']}"],
            }
        )

    signals.sort(key=lambda s: (s["observed_at"], s["signal_id"]), reverse=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        for s in signals:
            fh.write(json.dumps(s, ensure_ascii=False) + "\n")

    from collections import Counter

    by_skill = Counter(s["canonical_skill_id"] for s in signals)
    metrics = {
        "signals": len(signals),
        "events_used": len(events),
        "distinct_skills": len(by_skill),
        "top_skills": by_skill.most_common(5),
        "latest": signals[0]["observed_at"] if signals else "",
    }
    run.finish({k: v for k, v in metrics.items() if k != "top_skills"})
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sigbuild")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    parser.parse_args(argv)
    print(json.dumps(cmd_build(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
