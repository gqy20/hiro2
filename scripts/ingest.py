"""ingest: 原始数据登记、manifest 与首层结构化（roadmap D0-D1）。

用法：
    uv run scripts/ingest.py manifest <source_id>
    uv run scripts/ingest.py excel
    uv run scripts/ingest.py wechat
    uv run scripts/ingest.py jd

原则：data/raw 只读；结果写入 data/processed/<source_id>/；运行记录写入 data/runs/。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from parsers import parse_matrix, sha256_of, stage_wechat  # noqa: E402
from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCES_FILE = ROOT / "data" / "SOURCES.yml"
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"


def load_sources() -> dict[str, dict]:
    data = yaml.safe_load(SOURCES_FILE.read_text(encoding="utf-8"))
    return {s["id"]: s for s in data["sources"]}


# ---------------------------------------------------------------- manifest


def cmd_manifest(source_id: str) -> dict:
    run = RunContext("ingest", {"cmd": "manifest", "source_id": source_id})
    sources = load_sources()
    if source_id not in sources:
        run.log("manifest", "source_lookup", "FAILED", detail=f"unknown source {source_id}")
        run.finish({}, "FAILED")
        raise SystemExit(2)
    src = sources[source_id]
    src_dir = ROOT / src["path"]
    files = sorted(p for p in src_dir.rglob("*") if p.is_file())
    records = [
        {"path": str(p.relative_to(ROOT)), "bytes": p.stat().st_size, "sha256": sha256_of(p)}
        for p in files
    ]
    out_dir = PROCESSED / source_id
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "manifest.json").write_text(
        json.dumps(
            {
                "source_id": source_id,
                "source_type": src["type"],
                "ingestion_mode": src["ingestion_mode"],
                "file_count": len(records),
                "total_bytes": sum(r["bytes"] for r in records),
                "files": records,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    run.log("manifest", "hashed", "succeeded", count=len(records))
    run.finish({"source_id": source_id, "file_count": len(records)})
    return {"source_id": source_id, "file_count": len(records)}


# ---------------------------------------------------------------- excel / wechat


def cmd_excel() -> dict:
    run = RunContext("ingest", {"cmd": "excel"})
    src = load_sources()["capability-matrix"]
    xlsx = next((ROOT / src["path"]).glob("*.xlsx"))
    parsed = parse_matrix(xlsx)

    out = PROCESSED / "capability-matrix"
    out.mkdir(parents=True, exist_ok=True)
    (out / "capabilities.json").write_text(
        json.dumps(
            {
                "capabilities": parsed["capabilities"],
                "groups": parsed["groups"],
                "score_legend": parsed["score_legend"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (out / "positions.jsonl").open("w", encoding="utf-8") as fh:
        for p in parsed["positions"]:
            fh.write(json.dumps(p, ensure_ascii=False) + "\n")

    counts = {
        "positions": len(parsed["positions"]),
        "capabilities": len(parsed["capabilities"]),
        "groups": len(parsed["groups"]),
    }
    ok = counts == {"positions": 46, "capabilities": 30, "groups": 7} and not parsed["issues"]
    run.log(
        "excel",
        "parsed",
        "succeeded" if ok else "FAILED",
        count=counts,
        detail=f"{len(parsed['issues'])} 个问题",
    )
    run.finish({**counts, "issues": len(parsed["issues"])})
    return counts


def cmd_wechat() -> dict:
    run = RunContext("ingest", {"cmd": "wechat"})
    staged = stage_wechat(RAW / "wechat-mp" / "out")

    out = PROCESSED / "wechat-mp"
    out.mkdir(parents=True, exist_ok=True)
    for name, records in (
        ("reports.jsonl", staged["reports"]),
        ("reports-unindexed.jsonl", staged["unindexed"]),
    ):
        with (out / name).open("w", encoding="utf-8") as fh:
            for item in records:
                fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    (out / "issues.json").write_text(
        json.dumps(
            {"issues": staged["issues"], "unindexed_count": len(staged["unindexed"])},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    run.log("wechat", "staged", "succeeded", count=staged["metrics"])
    run.finish(staged["metrics"])
    return staged["metrics"]


# ---------------------------------------------------------------- jd


def cmd_jd() -> dict:
    run = RunContext("ingest", {"cmd": "jd"})
    jd_dir = RAW / "jd" / "opencli"
    search = [json.loads(x) for x in (jd_dir / "jd_opencli_raw.jsonl").open(encoding="utf-8")]
    details = [
        json.loads(x) for x in (jd_dir / "jd_opencli_detail_raw.jsonl").open(encoding="utf-8")
    ]

    def desc_len(rec: dict) -> int:
        det = rec.get("detail")
        if isinstance(det, str):
            try:
                import ast

                det = ast.literal_eval(det)
            except (ValueError, SyntaxError):
                return 0
        return len(det.get("description") or "") if isinstance(det, dict) else 0

    # 51job 与 boss 的搜索行字段不同：jobId/security_id、title/name、issueDate 仅 51job 有
    def rec_id(r: dict) -> str:
        return r.get("jobId") or r.get("security_id") or "?"

    dates = sorted(r["issueDate"][:10] for r in search if r.get("issueDate"))
    dup_ids = [k for k, v in Counter(rec_id(r) for r in search).items() if v > 1]
    metrics = {
        "search_total": len(search),
        "search_by_platform": dict(Counter(r.get("source_platform", "?") for r in search)),
        "search_by_keyword": dict(Counter(r.get("keyword", "?") for r in search)),
        "search_missing_title": sum(1 for r in search if not (r.get("title") or r.get("name"))),
        "search_duplicate_ids": len(dup_ids),
        "search_missing_publish_date": sum(1 for r in search if not r.get("issueDate")),
        "date_range": [dates[0], dates[-1]] if dates else [],
        "detail_total": len(details),
        "detail_status": dict(Counter(r.get("status", "?") for r in details)),
        "detail_desc_usable_ge200": sum(1 for r in details if desc_len(r) >= 200),
        "detail_desc_insufficient": sum(1 for r in details if desc_len(r) < 200),
        "detail_title_broken": sum(
            1
            for r in details
            if isinstance(r.get("detail"), dict) and r["detail"].get("title") == "APP下载"
        ),
    }
    out = PROCESSED / "jd-opencli"
    out.mkdir(parents=True, exist_ok=True)
    (out / "stats.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    run.log("jd", "staged", "succeeded", count=metrics["search_total"])
    run.finish(metrics)
    return metrics


# ---------------------------------------------------------------- cli


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ingest")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("excel")
    sub.add_parser("wechat")
    sub.add_parser("jd")
    p_manifest = sub.add_parser("manifest")
    p_manifest.add_argument("source_id")
    args = parser.parse_args(argv)

    if args.cmd == "excel":
        result = cmd_excel()
    elif args.cmd == "wechat":
        result = cmd_wechat()
    elif args.cmd == "jd":
        result = cmd_jd()
    else:
        result = cmd_manifest(args.source_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
