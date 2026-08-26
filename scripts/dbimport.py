"""dbimport: JSONL 产物导入 PostgreSQL（Phase B 数据管道）。

用法：
    uv run scripts/dbimport.py run [--dsn postgresql://...]

导入源（processed 产物，幂等 UPSERT）：
    sources         <- data/SOURCES.yml
    capabilities    <- capability-matrix/capabilities.json
    skills          <- SKILLS.yml + SKILLS-EARNED.yml
    evidence        <- evidence/evidence.jsonl
    report_events   <- wechat-mp/events.jsonl
    jd_records      <- jd-opencli/jd-parsed.jsonl
    job_versions    <- jobversions/published/*.json
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
DEFAULT_DSN = "postgresql://postgres@localhost:5432/hiro2"


def _load_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.open(encoding="utf-8")] if p.is_file() else []


def _load_json(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def cmd_run(dsn: str) -> dict:
    import psycopg

    run = RunContext("dbimport", {"cmd": "run"})
    counts: dict[str, int] = {}

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # ---- sources ----
            srcs = yaml.safe_load((ROOT / "data" / "SOURCES.yml").read_text(encoding="utf-8"))["sources"]
            for s in srcs:
                cur.execute(
                    """INSERT INTO sources (source_id, source_type, license, time_range, ingestion_mode, notes)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (source_id) DO UPDATE SET source_type=EXCLUDED.source_type, notes=EXCLUDED.notes""",
                    (s["id"], s["type"], s.get("license", ""), s.get("time_range", []),
                     s.get("ingestion_mode", "backfill"), s.get("notes", "")),
                )
            # 补登 evidence 使用的平台级 source_id
            for extra in ("51job", "boss"):
                cur.execute(
                    "INSERT INTO sources (source_id, source_type, license) VALUES (%s, 'job_board', 'platform') ON CONFLICT DO NOTHING",
                    (extra,),
                )
            counts["sources"] = len(srcs) + 2

            # ---- capabilities ----
            caps = _load_json(P / "capability-matrix" / "capabilities.json").get("capabilities", [])
            for i, c in enumerate(caps):
                cur.execute(
                    "INSERT INTO capabilities (capability_id, name, group_name, sort_order) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                    (c["capability_id"], c["name"], c.get("group", ""), i),
                )
            counts["capabilities"] = len(caps)

            # ---- skills ----
            skills_yml = yaml.safe_load((ROOT / "data" / "SKILLS.yml").read_text(encoding="utf-8"))
            n_skills = 0
            for entry in skills_yml["entries"]:
                cap = entry["capability_id"]
                cur.execute(
                    "INSERT INTO skills (skill_id, capability_id, aliases, rule_version, is_earned) VALUES (%s,%s,%s,%s,FALSE) ON CONFLICT DO NOTHING",
                    (cap, cap, entry.get("aliases", []), skills_yml["version"]),
                )
                n_skills += 1
                for pt, _aliases in entry.get("points", []):
                    cur.execute(
                        "INSERT INTO skills (skill_id, capability_id, point_name, rule_version, is_earned) VALUES (%s,%s,%s,%s,FALSE) ON CONFLICT DO NOTHING",
                        (f"{cap}.{pt}", cap, pt, skills_yml["version"]),
                    )
                    n_skills += 1
            earned_yml = yaml.safe_load((ROOT / "data" / "SKILLS-EARNED.yml").read_text(encoding="utf-8"))
            for ea in earned_yml.get("aliases", []):
                cur.execute(
                    """INSERT INTO skills (skill_id, capability_id, point_name, rule_version, effective_from, is_earned)
                       VALUES (%s,%s,%s,%s,%s,TRUE) ON CONFLICT (skill_id) DO UPDATE SET effective_from=EXCLUDED.effective_from""",
                    (ea["mention"], ea["capability_id"], ea.get("point_name"),
                     earned_yml.get("version", 1), ea.get("effective_from")),
                )
                n_skills += 1
            counts["skills"] = n_skills

            # ---- evidence ----
            evs = _load_jsonl(P / "evidence" / "evidence.jsonl")
            for e in evs:
                cur.execute(
                    """INSERT INTO evidence (evidence_id, source_id, claim_type, published_at, content_hash, quality_score, payload, urls, source_span)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (evidence_id) DO UPDATE SET quality_score=EXCLUDED.quality_score, payload=EXCLUDED.payload""",
                    (e["evidence_id"], e["source_id"], e["claim_type"], e.get("published_at"),
                     e.get("content_hash", ""), e.get("quality_score", 0.5),
                     json.dumps(e.get("payload", {})), e.get("urls", []),
                     json.dumps(e.get("source_span", {}))),
                )
            counts["evidence"] = len(evs)

            # ---- report_events ----
            events = [e for e in _load_jsonl(P / "wechat-mp" / "events.jsonl") if e.get("is_primary", True)]
            for e in events:
                cur.execute(
                    """INSERT INTO report_events (event_id, item_id, event_type, title, summary, entities, fact_grade, skill_mentions, urls, published_at, is_primary, duplicate_group_id, prompt_version, model_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s,%s,%s)
                       ON CONFLICT (event_id) DO UPDATE SET skill_mentions=EXCLUDED.skill_mentions""",
                    (e["event_id"], e["item_id"], e.get("event_type", ""), e.get("title", ""),
                     e.get("summary", ""), e.get("entities", []), e.get("fact_grade", "report"),
                     e.get("skill_mentions", []), e.get("urls", []),
                     (e.get("published_at") or "")[:10] or None,
                     e.get("duplicate_group_id"), e.get("prompt_version"), e.get("model_version")),
                )
            counts["report_events"] = len(events)

            # ---- jd_records ----
            jds = _load_jsonl(P / "jd-opencli" / "jd-parsed.jsonl")
            for r in jds:
                cur.execute(
                    """INSERT INTO jd_records (jd_id, platform, title, is_ai_role, domain_reason, publish_date, city, salary, work_year, responsibilities, requirements, skill_mentions, resolved)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (jd_id) DO UPDATE SET skill_mentions=EXCLUDED.skill_mentions, resolved=EXCLUDED.resolved""",
                    (r["jd_id"], r["platform"], r["title"], r.get("is_ai_role", True),
                     r.get("domain_reason", ""), r.get("publish_date"), r.get("city"),
                     r.get("salary", ""), r.get("work_year", ""),
                     json.dumps(r.get("responsibilities", [])), json.dumps(r.get("requirements", [])),
                     r.get("skill_mentions", []), json.dumps(r.get("resolved", []))),
                )
            counts["jd_records"] = len(jds)

            # ---- job_versions（仅 PUBLISHED）----
            pub_dir = P / "jobversions" / "published"
            n_jv = 0
            if pub_dir.is_dir():
                for f in pub_dir.glob("*.json"):
                    v = _load_json(f)
                    cur.execute(
                        """INSERT INTO jobs (job_id, title) VALUES (%s,%s) ON CONFLICT DO NOTHING""",
                        (v["job_id"], v["title"]),
                    )
                    cur.execute(
                        """INSERT INTO job_versions (version_id, job_id, status, title, required_skills, preferred_skills, changeset, evidence_ids, version_hash, valid_from, published_at)
                           VALUES (%s,%s,'PUBLISHED',%s,%s,%s,%s,%s,%s,%s,%s)
                           ON CONFLICT (version_id) DO NOTHING""",
                        (v["version_id"], v["job_id"], v["title"],
                         json.dumps(v.get("required_skill_ids", [])),
                         json.dumps(v.get("preferred_skill_ids", [])),
                         json.dumps(v.get("changeset_vs_v1", [])),
                         v.get("evidence", {}).get("evidence_ids", []),
                         v.get("version_hash", ""),
                         v.get("valid_from"), v.get("published_at")),
                    )
                    n_jv += 1
            counts["job_versions"] = n_jv

            # ---- review_tasks（由冻结评测集生成，幂等） ----
            manifest = _load_json(ROOT / "evaluation" / "samples" / "manifest.json")
            dataset_version = manifest.get("dataset_version", "")
            task_specs = (
                ("role-mapping.csv", "role_level", "jd_id"),
                ("domain-judgment.csv", "evidence_audit", "jd_id"),
                ("event-extraction.csv", "skill_mapping", "event_id"),
            )
            n_tasks = 0
            for filename, task_type, id_field in task_specs:
                sample_path = ROOT / "evaluation" / "samples" / filename
                if not sample_path.is_file():
                    continue
                with sample_path.open(encoding="utf-8-sig", newline="") as fh:
                    for row in csv.DictReader(fh):
                        source_id = row.get(id_field, "")
                        if not source_id:
                            continue
                        task_id = f"task-{task_type}-{source_id}"
                        verdict_col = next((key for key in row if "?" in key), "")
                        status = "RESOLVED" if row.get(verdict_col, "").strip() else "PENDING"
                        cur.execute(
                            """
                            INSERT INTO review_tasks
                                (task_id, task_type, source_record_id, dataset_version, status, system_output)
                            VALUES (%s,%s,%s,%s,%s,%s)
                            ON CONFLICT (task_id) DO UPDATE
                            SET status = CASE
                                WHEN review_tasks.status = 'PENDING' THEN EXCLUDED.status
                                ELSE review_tasks.status
                            END
                            """,
                            (task_id, task_type, source_id, dataset_version, status,
                             json.dumps({"title": row.get("职位名", row.get("标题", ""))})),
                        )
                        n_tasks += 1
            counts["review_tasks"] = n_tasks

        conn.commit()

    run.log("dbimport", "finished", "succeeded", count=counts)
    run.finish(counts)
    return counts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="dbimport")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--dsn", default=DEFAULT_DSN)
    args = parser.parse_args(argv)
    result = cmd_run(args.dsn)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
