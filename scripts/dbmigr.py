"""dbmigr: apply immutable SQL migrations once, in lexical order."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = ROOT / "migrations"


def main() -> None:
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        raise SystemExit("需要 DATABASE_URL，例如 postgresql://hiro2:hiro2@localhost:5432/hiro2")
    import psycopg

    files = sorted(MIGRATIONS.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_xact_lock(26082026)")
        cur.execute(
            """CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )"""
        )
        cur.execute("SELECT version FROM schema_migrations")
        applied = {row[0] for row in cur.fetchall()}
        for file in files:
            if file.name in applied:
                continue
            cur.execute(file.read_text(encoding="utf-8"))
            cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (file.name,))
            print(f"applied {file.name}")


if __name__ == "__main__":
    main()
