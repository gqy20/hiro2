"""Run the five deterministic data-quality gates and emit one JSON report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
OUT = ROOT / "data" / "runs"


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def completeness() -> dict:
    events = _jsonl(P / "wechat-mp" / "events.jsonl")
    required = ("event_id", "title", "published_at")
    missing = sum(
        any(not e.get(field) for field in required) or not (e.get("urls") or e.get("item_id"))
        for e in events
    )
    return {
        "status": "pass" if events and not missing else "warn",
        "checked": len(events),
        "failed": missing,
    }


def deduplication() -> dict:
    stats_path = P / "wechat-mp" / "dedup-stats.json"
    stats = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.is_file() else {}
    duplicate_events = int(stats.get("duplicate_events", 0))
    return {
        "status": "pass" if stats else "warn",
        "checked": stats.get("events", 0),
        "duplicate_events": duplicate_events,
        "duplicate_ratio": stats.get("duplicate_ratio"),
    }


def timeliness() -> dict:
    events = _jsonl(P / "wechat-mp" / "events.jsonl")
    future = 0
    for event in events:
        if event.get("as_of_date") and event.get("published_at", "")[:10] > event["as_of_date"]:
            future += 1
    return {
        "status": "pass" if not future else "fail",
        "checked": len(events),
        "future_records": future,
    }


def cross_validation() -> dict:
    path = P / "wechat-mp" / "leadtime.json"
    rows = json.loads(path.read_text(encoding="utf-8")).get("rows", []) if path.is_file() else []
    clean = sum(row.get("reliability") == "clean" for row in rows)
    return {"status": "pass" if clean else "warn", "checked": len(rows), "clean_rows": clean}


def hallucination_guard() -> dict:
    draft_path = P / "jd-opencli" / "jobversion-agent-draft.json"
    draft = json.loads(draft_path.read_text(encoding="utf-8")) if draft_path.is_file() else {}
    changes = draft.get("changeset_vs_v1", [])
    missing = sum(
        not (
            change.get("evidence_ids")
            or change.get("evidenceIds")
            or change.get("evidence_jd_count")
        )
        for change in changes
    )
    return {
        "status": "pass" if changes and not missing else "warn",
        "checked": len(changes),
        "without_evidence": missing,
    }


def run() -> dict:
    context = RunContext("quality", {"cmd": "run"})
    gates = {
        "completeness": completeness(),
        "deduplication": deduplication(),
        "timeliness": timeliness(),
        "cross_validation": cross_validation(),
        "hallucination_guard": hallucination_guard(),
    }
    statuses = [gate["status"] for gate in gates.values()]
    status = "fail" if "fail" in statuses else "warn" if "warn" in statuses else "pass"
    report = {"run_id": context.run_id, "gates": gates, "overall_status": status}
    run_dir = OUT / context.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "quality-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    context.finish(
        {
            "overall_status": status,
            **{f"{name}_status": gate["status"] for name, gate in gates.items()},
        }
    )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="quality")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    args = parser.parse_args(argv)
    if args.cmd == "run":
        print(json.dumps(run(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
