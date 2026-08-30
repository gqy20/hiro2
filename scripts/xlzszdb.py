"""xlzszdb: 学练赛证实体入 PostgreSQL（migration 0009 三表）。

用法：
    uv run scripts/xlzszdb.py run                # cert/race 目录 + std_requirements 全量导入
    uv run scripts/xlzszdb.py run --table certs  # 只导证书目录

输入（certget/raceget/certparse 产物，data/processed/）：
    certs/cert-catalog.jsonl          2050 条证书目录
    races/race-catalog.jsonl          1199 条竞赛目录
    certs/std-requirements/*.jsonl    10 份标准工作要求表（569 行）

幂等：INSERT ... ON CONFLICT DO UPDATE（目录全量重写语义）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _to_date(v: str | None) -> date | None:
    if not v or not isinstance(v, str):
        return None
    m = _DATE_RE.match(v.strip())
    return date.fromisoformat(m.group(0)) if m else None


def _to_int(v) -> int | None:
    try:
        return int(str(v)) if v not in (None, "") else None
    except (ValueError, TypeError):
        return None


def import_certs(cur) -> int:
    path = P / "certs" / "cert-catalog.jsonl"
    n = 0
    if path.is_file():
        for line in path.open(encoding="utf-8"):
            r = json.loads(line)
            cur.execute(
                """INSERT INTO cert_catalog
                   (cert_id, name, cert_type, issuer, level, career_code,
                    effective_from, description, doc_number, source, source_url)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (cert_id) DO UPDATE SET
                     name=EXCLUDED.name, level=EXCLUDED.level,
                     description=EXCLUDED.description, effective_from=EXCLUDED.effective_from""",
                (
                    r["cert_id"],
                    r.get("name") or "",
                    r.get("type") or "",
                    r.get("issuer") or "",
                    r.get("level") or "",
                    r.get("career_code") or "",
                    _to_date(r.get("effective_from")),
                    (r.get("description") or r.get("introduction") or "")[:2000],
                    r.get("doc_number") or "",
                    r.get("source") or "",
                    r.get("source_url") or "",
                ),
            )
            n += 1
    return n


def import_races(cur) -> int:
    path = P / "races" / "race-catalog.jsonl"
    n = 0
    if path.is_file():
        for line in path.open(encoding="utf-8"):
            r = json.loads(line)
            cur.execute(
                """INSERT INTO race_catalog
                   (race_id, name, race_type, industry, organizer, bonus, team_count,
                    register_end, final_end, tags, description, source, source_url)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (race_id) DO UPDATE SET
                     name=EXCLUDED.name, team_count=EXCLUDED.team_count,
                     register_end=EXCLUDED.register_end, tags=EXCLUDED.tags""",
                (
                    r["race_id"],
                    r.get("name") or "",
                    r.get("type") or "",
                    r.get("industry") or "",
                    r.get("organizer") or "",
                    str(r.get("bonus") or ""),
                    _to_int(r.get("team_count")),
                    _to_date(r.get("register_end")),
                    _to_date(r.get("final_end")),
                    r.get("tags") or [],
                    (r.get("description") or "")[:2000],
                    r.get("source") or "",
                    r.get("source_url") or "",
                ),
            )
            n += 1
    return n


def import_std_requirements(cur) -> int:
    n = 0
    std_dir = P / "certs" / "std-requirements"
    if std_dir.is_dir():
        for f in sorted(std_dir.glob("*.jsonl")):
            code = f.stem
            for line in f.open(encoding="utf-8"):
                r = json.loads(line)
                cur.execute(
                    """INSERT INTO std_requirements
                       (career_code, level, func, work_no, work, skills, knowledge)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (career_code, level, work_no) DO UPDATE SET
                         work=EXCLUDED.work, skills=EXCLUDED.skills,
                         knowledge=EXCLUDED.knowledge""",
                    (
                        code,
                        r.get("level") or "",
                        r.get("func") or "",
                        r.get("work_no") or "",
                        r.get("work") or "",
                        r.get("skills") or [],
                        r.get("knowledge") or [],
                    ),
                )
                n += 1
    return n


def cmd_run(dsn: str, table: str | None) -> dict:
    import psycopg

    run = RunContext("xlzszdb", {"cmd": "run", "table": table})
    counts: dict[str, int] = {}
    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            if table in (None, "certs"):
                counts["cert_catalog"] = import_certs(cur)
            if table in (None, "races"):
                counts["race_catalog"] = import_races(cur)
            if table in (None, "std"):
                counts["std_requirements"] = import_std_requirements(cur)
        conn.commit()

    for table_name, n in counts.items():
        run.log(table_name, "imported", "SUCCEEDED", count={"rows": n})
    run.finish(counts)
    return counts


def main(argv: list[str] | None = None) -> int:
    import os

    parser = argparse.ArgumentParser(prog="xlzszdb")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--dsn", default=os.environ.get("DATABASE_URL", ""))
    p_run.add_argument("--table", choices=["certs", "races", "std"], default=None)
    args = parser.parse_args(argv)

    if not args.dsn:
        print("需要 --dsn 或 DATABASE_URL 环境变量", file=sys.stderr)
        return 1
    result = cmd_run(args.dsn, args.table)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
