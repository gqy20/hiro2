"""pgcheck: 容器内 PG 状态快速诊断。"""

import json
import os

import psycopg

with psycopg.connect(os.environ["DATABASE_URL"]) as conn, conn.cursor() as cur:
    cur.execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY 1"
    )
    tables = [r[0] for r in cur.fetchall()]
    result = {}
    for t in tables:
        cur.execute(f'SELECT count(*) FROM "{t}"')
        result[t] = cur.fetchone()[0]
    print(json.dumps(result, ensure_ascii=False, indent=1))
