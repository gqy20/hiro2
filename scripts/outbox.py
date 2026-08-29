"""Enqueue a JobVersionPublished event for the Neo4j projector."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.outbox import consume_batch, enqueue_event  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="outbox")
    sub = parser.add_subparsers(dest="cmd", required=True)
    enqueue = sub.add_parser("enqueue")
    enqueue.add_argument("version_id")
    enqueue.add_argument("--dsn", default=os.getenv("DATABASE_URL", ""))
    consume = sub.add_parser("consume")
    consume.add_argument("--dsn", default=os.getenv("DATABASE_URL", ""))
    consume.add_argument("--limit", type=int, default=20)
    args = parser.parse_args(argv)
    if not args.dsn:
        parser.error("需要 --dsn 或 DATABASE_URL")
    if args.cmd == "consume":
        print(json.dumps(consume_batch(args.dsn, max(1, args.limit)), ensure_ascii=False))
        return 0
    event_id = enqueue_event(
        args.dsn,
        "JobVersionPublished",
        "JobVersion",
        args.version_id,
        {"version_id": args.version_id},
    )
    print(json.dumps({"event_id": event_id, "status": "PENDING"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
