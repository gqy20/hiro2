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
import hashlib
import json
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
DEFAULT_DSN = os.getenv("DATABASE_URL", "postgresql://hiro2:hiro2@localhost:5433/hiro2")


def _load_jsonl(p: Path) -> list[dict]:
    return [json.loads(x) for x in p.open(encoding="utf-8")] if p.is_file() else []


def _load_json(p: Path) -> dict:
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.open(encoding="utf-8", errors="ignore") if line.strip())


def _manifest_version(path: Path) -> str:
    payload = _load_json(path)
    return str(payload.get("dataset_version") or payload.get("version") or payload.get("batch") or "")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    if not path.is_file():
        return ""
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _register_dataset(
    cur,
    *,
    dataset_id: str,
    version: str,
    record_count: int,
    valid_count: int,
    quality: float,
    manifest_path: Path,
    run_id: str,
    status: str = "IMPORTED",
) -> None:
    manifest = _load_json(manifest_path)
    pending = max(0, record_count - valid_count)
    cur.execute(
        """
        INSERT INTO dataset_versions
            (dataset_id, dataset_version, status, record_count, valid_record_count,
             pending_record_count, quality_score, manifest_hash, manifest, run_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (dataset_id, dataset_version) DO UPDATE SET
            status=EXCLUDED.status, record_count=EXCLUDED.record_count,
            valid_record_count=EXCLUDED.valid_record_count,
            pending_record_count=EXCLUDED.pending_record_count,
            quality_score=EXCLUDED.quality_score, manifest_hash=EXCLUDED.manifest_hash,
            manifest=EXCLUDED.manifest, run_id=EXCLUDED.run_id, imported_at=now()
        """,
        (
            dataset_id, version, status, record_count, valid_count, pending,
            quality, _sha256(manifest_path), json.dumps(manifest), run_id,
        ),
    )


def cmd_run(dsn: str) -> dict:
    import psycopg

    run = RunContext("dbimport", {"cmd": "run"})
    counts: dict[str, int] = {}

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            # ---- sources ----
            srcs = yaml.safe_load((ROOT / "data" / "SOURCES.yml").read_text(encoding="utf-8"))[
                "sources"
            ]
            for s in srcs:
                cur.execute(
                    """INSERT INTO sources (source_id, source_type, license, time_range, ingestion_mode, notes)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (source_id) DO UPDATE SET source_type=EXCLUDED.source_type, notes=EXCLUDED.notes""",
                    (
                        s["id"],
                        s["type"],
                        s.get("license", ""),
                        s.get("time_range", []),
                        s.get("ingestion_mode", "backfill"),
                        s.get("notes", ""),
                    ),
                )
            # 补登 evidence 使用的平台级 source_id。处理产物可能包含未进入
            # SOURCES.yml 的企业招聘站标识，先登记再写入外键表。
            evidence_path = P / "evidence" / "evidence.jsonl"
            evidence_rows = _load_jsonl(evidence_path)
            configured_ids = {str(source.get("id", "")) for source in srcs}
            inferred_ids = {
                str(row.get("source_id", ""))
                for row in evidence_rows
                if row.get("source_id")
            }
            platform_ids = {"51job", "boss"} | (inferred_ids - configured_ids)
            for extra in sorted(platform_ids):
                cur.execute(
                    "INSERT INTO sources (source_id, source_type, license, notes) VALUES (%s, 'job_board', 'platform', '从处理产物推断的平台来源') ON CONFLICT DO NOTHING",
                    (extra,),
                )
            counts["sources"] = len(srcs) + len(platform_ids - configured_ids)

            # ---- dataset_versions（导入快照登记，幂等） ----
            dataset_specs = (
                ("jd", _manifest_version(P / "jd-opencli" / "manifest.json") or "jd-v3", P / "jd-opencli" / "norm-jd.jsonl", P / "jd-opencli" / "manifest.json"),
                ("temporal", _manifest_version(P / "wechat-mp" / "manifest.json") or "temporal-v2", P / "wechat-mp" / "events.jsonl", P / "wechat-mp" / "manifest.json"),
                ("capability", _manifest_version(P / "capability-matrix" / "manifest.json") or "skill-v6", P / "capability-matrix" / "position-skills.jsonl", P / "capability-matrix" / "manifest.json"),
                ("evidence", _manifest_version(P / "evidence" / "manifest.json") or "evidence-v2", P / "evidence" / "evidence.jsonl", P / "evidence" / "manifest.json"),
                ("evaluation", "eval-v1-20260825", ROOT / "evaluation" / "samples" / "manifest.json", ROOT / "evaluation" / "samples" / "manifest.json"),
                ("resumes", "resume-v2", P / "candidates" / "resume-archive.jsonl", P / "candidates" / "resume-archive.jsonl"),
            )
            for dataset_id, version, record_path, manifest_path in dataset_specs:
                records = _line_count(record_path) if record_path.suffix == ".jsonl" else sum(
                    max(0, _line_count(ROOT / "evaluation" / "samples" / name) - 1)
                    for name in ("role-mapping.csv", "domain-judgment.csv", "event-extraction.csv")
                ) if dataset_id == "evaluation" else 0
                valid_count = records
                if dataset_id == "resumes":
                    archive_rows = _load_jsonl(record_path)
                    latest_rows = {
                        str(row.get("resume_id")): row
                        for row in archive_rows
                        if row.get("resume_id")
                    }
                    records = len(latest_rows)
                    valid_count = sum(bool(row.get("profile")) for row in latest_rows.values())
                _register_dataset(
                    cur, dataset_id=dataset_id, version=version, record_count=records,
                    valid_count=valid_count, quality=0.67 if dataset_id == "resumes" else 1.0,
                    manifest_path=manifest_path, run_id=run.run_id,
                    status="FROZEN" if dataset_id == "evaluation" else "IMPORTED",
                )
            counts["dataset_versions"] = len(dataset_specs)

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
            earned_yml = yaml.safe_load(
                (ROOT / "data" / "SKILLS-EARNED.yml").read_text(encoding="utf-8")
            )
            for ea in earned_yml.get("aliases", []):
                cur.execute(
                    """INSERT INTO skills (skill_id, capability_id, point_name, rule_version, effective_from, is_earned)
                       VALUES (%s,%s,%s,%s,%s,TRUE) ON CONFLICT (skill_id) DO UPDATE SET effective_from=EXCLUDED.effective_from""",
                    (
                        ea["mention"],
                        ea["capability_id"],
                        ea.get("point_name"),
                        earned_yml.get("version", 1),
                        ea.get("effective_from"),
                    ),
                )
                n_skills += 1
            counts["skills"] = n_skills

            # ---- evidence ----
            evs = evidence_rows
            for e in evs:
                cur.execute(
                    """INSERT INTO evidence (evidence_id, source_id, claim_type, published_at, content_hash, quality_score, payload, urls, source_span)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (evidence_id) DO UPDATE SET quality_score=EXCLUDED.quality_score, payload=EXCLUDED.payload""",
                    (
                        e["evidence_id"],
                        e["source_id"],
                        e["claim_type"],
                        e.get("published_at"),
                        e.get("content_hash", ""),
                        e.get("quality_score", 0.5),
                        json.dumps(e.get("payload", {})),
                        e.get("urls", []),
                        json.dumps(e.get("source_span", {})),
                    ),
                )
            counts["evidence"] = len(evs)

            # ---- report_events ----
            events = [
                e
                for e in _load_jsonl(P / "wechat-mp" / "events.jsonl")
                if e.get("is_primary", True)
            ]
            for e in events:
                cur.execute(
                    """INSERT INTO report_events (event_id, item_id, event_type, title, summary, entities, fact_grade, skill_mentions, urls, published_at, is_primary, duplicate_group_id, prompt_version, model_version)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s,%s,%s)
                       ON CONFLICT (event_id) DO UPDATE SET skill_mentions=EXCLUDED.skill_mentions""",
                    (
                        e["event_id"],
                        e["item_id"],
                        e.get("event_type", ""),
                        e.get("title", ""),
                        e.get("summary", ""),
                        e.get("entities", []),
                        e.get("fact_grade", "report"),
                        e.get("skill_mentions", []),
                        e.get("urls", []),
                        (e.get("published_at") or "")[:10] or None,
                        e.get("duplicate_group_id"),
                        e.get("prompt_version"),
                        e.get("model_version"),
                    ),
                )
            counts["report_events"] = len(events)

            # ---- jd_records ----
            jds = _load_jsonl(P / "jd-opencli" / "jd-parsed.jsonl")
            for r in jds:
                cur.execute(
                    """INSERT INTO jd_records (jd_id, platform, title, is_ai_role, domain_reason, publish_date, city, salary, work_year, responsibilities, requirements, skill_mentions, resolved)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (jd_id) DO UPDATE SET skill_mentions=EXCLUDED.skill_mentions, resolved=EXCLUDED.resolved""",
                    (
                        r["jd_id"],
                        r["platform"],
                        r["title"],
                        r.get("is_ai_role", True),
                        r.get("domain_reason", ""),
                        r.get("publish_date"),
                        r.get("city"),
                        r.get("salary", ""),
                        r.get("work_year", ""),
                        json.dumps(r.get("responsibilities", [])),
                        json.dumps(r.get("requirements", [])),
                        r.get("skill_mentions", []),
                        json.dumps(r.get("resolved", [])),
                    ),
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
                        (
                            v["version_id"],
                            v["job_id"],
                            v["title"],
                            json.dumps(v.get("required_skill_ids", [])),
                            json.dumps(v.get("preferred_skill_ids", [])),
                            json.dumps(v.get("changeset_vs_v1", [])),
                            v.get("evidence", {}).get("evidence_ids", []),
                            v.get("version_hash", ""),
                            v.get("valid_from"),
                            v.get("published_at"),
                        ),
                    )
                    cur.execute(
                        """
                        INSERT INTO outbox_events
                            (event_id, event_type, aggregate_type, aggregate_id, payload)
                        VALUES (%s, 'JobVersionPublished', 'JobVersion', %s, %s)
                        ON CONFLICT (event_id) DO NOTHING
                        """,
                        (
                            f"job-published:{v['version_id']}",
                            v["version_id"],
                            json.dumps({"version_id": v["version_id"]}),
                        ),
                    )
                    n_jv += 1
            counts["job_versions"] = n_jv

            # ---- candidates + match_reports（个人成长任务的事实前提） ----
            candidate_dir = P / "candidates"
            candidate_files = sorted(candidate_dir.glob("*.json")) if candidate_dir.is_dir() else []
            for file in candidate_files:
                candidate = _load_json(file)
                candidate_id = candidate.get("candidate_id")
                if not candidate_id:
                    continue
                cur.execute(
                    """
                    INSERT INTO candidates (candidate_id, raw_extraction, effective_profile, correction_log)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (candidate_id) DO UPDATE
                    SET effective_profile = EXCLUDED.effective_profile,
                        correction_log = EXCLUDED.correction_log
                    """,
                    (
                        candidate_id,
                        json.dumps({"raw_extraction_id": candidate.get("raw_extraction_id", "")}),
                        json.dumps(candidate),
                        json.dumps(candidate.get("correction_log", [])),
                    ),
                )
            counts["candidates"] = len(candidate_files)

            match_dir = candidate_dir / "matches"
            match_files = sorted(match_dir.glob("*-report.json")) if match_dir.is_dir() else []
            n_reports = 0
            for file in match_files:
                report = _load_json(file)
                if not report.get("candidate_id") or not report.get("job_version_id"):
                    continue
                cur.execute(
                    """
                    INSERT INTO match_reports
                        (match_id, candidate_id, job_version_id, algorithm_version, overall_score,
                         dimensions, gaps, evidence_ids, status)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (match_id) DO UPDATE
                    SET overall_score = EXCLUDED.overall_score,
                        dimensions = EXCLUDED.dimensions,
                        gaps = EXCLUDED.gaps,
                        evidence_ids = EXCLUDED.evidence_ids
                    """,
                    (
                        report.get("match_id"),
                        report["candidate_id"],
                        report["job_version_id"],
                        report.get("algorithm_version", ""),
                        report.get("overall_score", 0),
                        json.dumps(report.get("dimensions", [])),
                        json.dumps(report.get("gaps", [])),
                        report.get("evidence_ids", []),
                        report.get("status", "FINAL"),
                    ),
                )
                n_reports += 1
            counts["match_reports"] = n_reports

            # ---- temporal：信号 / 回测 / 预测 / 岗位影响建议 ----
            signals = _load_jsonl(P / "temporal" / "signals.jsonl")
            for signal in signals:
                cur.execute(
                    """
                    INSERT INTO trend_signals
                        (signal_id, item_id, skill_id, signal_type, observed_at, confidence,
                         evidence_ids, payload)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (signal_id) DO UPDATE
                    SET confidence = EXCLUDED.confidence, evidence_ids = EXCLUDED.evidence_ids,
                        payload = EXCLUDED.payload
                    """,
                    (
                        signal["signal_id"],
                        signal["item_id"],
                        signal["canonical_skill_id"],
                        signal.get("signal_type", "mention"),
                        signal["observed_at"],
                        signal.get("confidence", 0.6),
                        signal.get("evidence_ids", []),
                        json.dumps(signal),
                    ),
                )
            counts["trend_signals"] = len(signals)

            latest_records: list[dict] = []
            for horizon in (30, 60, 90):
                backtest = _load_json(P / "wechat-mp" / f"backtest-h{horizon}.json")
                metrics = backtest.get("metrics", {})
                run_id = f"bt-h{horizon}"
                if not metrics:
                    continue
                cur.execute(
                    """
                    INSERT INTO pipeline_runs (run_id, run_type, status, dataset_version, metrics)
                    VALUES (%s, 'backtest', 'SUCCEEDED', 'wechat-mp', %s)
                    ON CONFLICT (run_id) DO UPDATE SET metrics = EXCLUDED.metrics, status = EXCLUDED.status
                    """,
                    (run_id, json.dumps(metrics)),
                )
                records = backtest.get("records", [])
                for record in records:
                    cur.execute(
                        """
                        INSERT INTO backtest_records
                            (run_id, as_of_date, skill_id, predicted_direction, actual_direction,
                             hit, confidence, recent, prior, rule_version)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (run_id, as_of_date, skill_id) DO UPDATE
                        SET predicted_direction = EXCLUDED.predicted_direction,
                            actual_direction = EXCLUDED.actual_direction, hit = EXCLUDED.hit,
                            confidence = EXCLUDED.confidence
                        """,
                        (
                            run_id,
                            record["as_of"],
                            record["skill_id"],
                            record["predicted"],
                            record["actual"],
                            record["hit"],
                            record.get("confidence", 0),
                            record.get("recent", 0),
                            record.get("prior", 0),
                            record.get("rule_version", 1),
                        ),
                    )
                if horizon == 30:
                    latest_records = records
            counts["backtest_records"] = len(latest_records)

            latest_as_of = max((record["as_of"] for record in latest_records), default="")
            for record in latest_records:
                if record["as_of"] != latest_as_of:
                    continue
                forecast_id = f"fct-{record['skill_id']}-{record['as_of']}"
                cur.execute(
                    """
                    INSERT INTO forecasts
                        (forecast_id, run_id, skill_id, as_of_date, horizon_days, predicted_direction,
                         predicted_heat, confidence, valid_until, rule_version)
                    VALUES (%s,'bt-h30',%s,%s,30,%s,%s,%s,%s,%s)
                    ON CONFLICT (forecast_id) DO UPDATE
                    SET predicted_direction = EXCLUDED.predicted_direction,
                        predicted_heat = EXCLUDED.predicted_heat, confidence = EXCLUDED.confidence
                    """,
                    (
                        forecast_id,
                        record["skill_id"],
                        record["as_of"],
                        record["predicted"],
                        record.get("recent", 0),
                        record.get("confidence", 0),
                        latest_as_of,
                        record.get("rule_version", 1),
                    ),
                )
            counts["forecasts"] = sum(record["as_of"] == latest_as_of for record in latest_records)

            leadtime = _load_json(P / "wechat-mp" / "leadtime.json")
            n_suggestions = 0
            for row in leadtime.get("rows", []):
                skill_id = row.get("capability_id")
                if not skill_id:
                    continue
                cur.execute(
                    """
                    INSERT INTO job_impact_suggestions
                        (suggestion_id, job_id, skill_id, change_type, reason)
                    VALUES (%s, 'job_pos_02_agent', %s, %s, %s)
                    ON CONFLICT (suggestion_id) DO UPDATE SET reason = EXCLUDED.reason
                    """,
                    (
                        f"sug-{skill_id}",
                        skill_id,
                        "promote" if row.get("lead_days", 0) > 200 else "add",
                        f"{row.get('name', skill_id)}：信号领先 {row.get('lead_days', 0)} 天（{row.get('reliability', '')}）",
                    ),
                )
                n_suggestions += 1
            counts["job_impact_suggestions"] = n_suggestions

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
                            (
                                task_id,
                                task_type,
                                source_id,
                                dataset_version,
                                status,
                                json.dumps({"title": row.get("职位名", row.get("标题", ""))}),
                            ),
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
