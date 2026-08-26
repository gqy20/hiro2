"""Enqueue a JobVersionPublished event for the Neo4j projector."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.outbox import enqueue_event  # noqa: E402
from backend.infra.neo4j import project_job_version  # noqa: E402


def _consume(dsn: str, limit: int) -> dict[str, int]:
    import psycopg

    processed = failed = 0
    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            """
            UPDATE outbox_events
            SET status = 'PROCESSING', attempts = attempts + 1
            WHERE event_id IN (
                SELECT event_id FROM outbox_events
                WHERE status = 'PENDING' AND available_at <= now()
                ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT %s
            )
            RETURNING event_id, event_type, aggregate_id, payload
            """,
            (limit,),
        ).fetchall()
        conn.commit()
        for event_id, event_type, aggregate_id, payload in rows:
            try:
                if event_type != "JobVersionPublished":
                    raise ValueError(f"unsupported event type: {event_type}")
                version_path = (
                    Path(__file__).resolve().parents[1]
                    / "data"
                    / "processed"
                    / "jobversions"
                    / "published"
                    / f"{aggregate_id}.json"
                )
                if not version_path.is_file():
                    raise FileNotFoundError(version_path)
                project_job_version(json.loads(version_path.read_text(encoding="utf-8")))
                conn.execute(
                    "UPDATE outbox_events SET status='SUCCEEDED', processed_at=%s "
                    "WHERE event_id=%s",
                    (datetime.now(UTC), event_id),
                )
                processed += 1
            except Exception as exc:
                conn.execute(
                    "UPDATE outbox_events SET status='FAILED', error_message=%s WHERE event_id=%s",
                    (str(exc)[:500], event_id),
                )
                failed += 1
        conn.commit()
    return {"processed": processed, "failed": failed}


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
        print(json.dumps(_consume(args.dsn, max(1, args.limit)), ensure_ascii=False))
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
