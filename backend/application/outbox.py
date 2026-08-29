"""Small PostgreSQL outbox writer; consumers remain independently rebuildable."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any


def enqueue_event(
    dsn: str,
    event_type: str,
    aggregate_type: str,
    aggregate_id: str,
    payload: dict[str, Any],
    event_id: str | None = None,
) -> str:
    event_id = event_id or str(uuid.uuid4())
    import psycopg

    with psycopg.connect(dsn) as conn:
        conn.execute(
            """
            INSERT INTO outbox_events
                (event_id, event_type, aggregate_type, aggregate_id, payload)
            VALUES (%s,%s,%s,%s,%s)
            ON CONFLICT (event_id) DO NOTHING
            """,
            (event_id, event_type, aggregate_type, aggregate_id, json.dumps(payload)),
        )
        conn.commit()
    return event_id


def retry_delay(attempts: int, base_seconds: int = 60) -> int:
    """失败重试退避：base * 2^(attempts-1)，封顶 1 小时。"""
    return min(base_seconds * (2 ** max(attempts - 1, 0)), 3600)


def consume_batch(
    dsn: str,
    limit: int = 20,
    max_attempts: int = 5,
    project=None,
) -> dict[str, int]:
    """消费一批 PENDING 事件 -> 投影 -> SUCCEEDED；失败带退避回 PENDING。

    project 可注入投影函数（单测用）；默认为 Neo4j 版本投影。
    FOR UPDATE SKIP LOCKED 保证多消费者安全；attempts 达上限转 FAILED 终态。
    """
    import psycopg

    if project is None:
        from backend.infra.neo4j import project_job_version

        project = project_job_version
    from datetime import UTC, datetime

    processed = retried = dead = 0
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
            RETURNING event_id, event_type, aggregate_id, payload, attempts
            """,
            (limit,),
        ).fetchall()
        conn.commit()
        for event_id, event_type, aggregate_id, payload, attempts in rows:
            try:
                if event_type != "JobVersionPublished":
                    raise ValueError(f"unsupported event type: {event_type}")
                version_path = (
                    Path(__file__).resolve().parents[2]
                    / "data/processed/jobversions/published"
                    / f"{aggregate_id}.json"
                )
                if not version_path.is_file():
                    raise FileNotFoundError(version_path)
                project(json.loads(version_path.read_text(encoding="utf-8")))
                conn.execute(
                    "UPDATE outbox_events SET status='SUCCEEDED', processed_at=%s "
                    "WHERE event_id=%s",
                    (datetime.now(UTC), event_id),
                )
                processed += 1
            except Exception as exc:  # noqa: BLE001 - 失败按退避回 PENDING 或终态
                if attempts < max_attempts:
                    conn.execute(
                        "UPDATE outbox_events SET status='PENDING', "
                        "available_at=now() + make_interval(secs => %s), "
                        "error_message=%s WHERE event_id=%s",
                        (retry_delay(attempts), str(exc)[:500], event_id),
                    )
                    retried += 1
                else:
                    conn.execute(
                        "UPDATE outbox_events SET status='FAILED', error_message=%s "
                        "WHERE event_id=%s",
                        (str(exc)[:500], event_id),
                    )
                    dead += 1
        conn.commit()
    return {"processed": processed, "retried": retried, "failed": dead}
