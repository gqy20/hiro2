"""Small PostgreSQL outbox writer; consumers remain independently rebuildable."""

from __future__ import annotations

import json
import uuid
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
