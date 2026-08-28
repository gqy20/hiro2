"""jdarchive: Wayback Machine 历史 JD 快照采集（回溯 2022~2025 真实岗位池）。

用法：
    uv run scripts/jdarchive.py run --site bytedance --from 2022 --to 2025
    uv run scripts/jdarchive.py run --site tencent  --from 2022 --to 2026

原理：CDX API 按 URL 前缀枚举目标招聘 API 的全部 200 快照（每个快照是当年
某次真实搜索的响应，~10 条/次），逐快照拉原始响应（id_ 模式，gzip 解压），
归一后带 snapshot_ts（观测时间）落盘。岗位跨快照重复时 jdxtract 按 jd_id
首见去重（采集按年份早->晚 append，首见=最早观测）。
限速：archive.org ~1 req/s。
产物：data/raw/jd/archive/<site>.jsonl
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from jdcorp import _normalize, _normalize_gh, _normalize_tx  # noqa: E402
from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "raw" / "jd" / "archive"
CDX = "http://web.archive.org/cdx/search/cdx"

# Greenhouse 历史快照集中在少数 board（figma 2022~2023 含正文版已验证）
GH_BOARDS = ["figma", "togetherai", "scaleai", "databricks", "stripe", "pinterest"]

SITES = {
    "bytedance": {
        "prefix": "jobs.bytedance.com/api/v1/search/job/posts*",
        "extract": lambda d: (d.get("data") or {}).get("job_post_list") or [],
        "normalize": _normalize,
    },
    "tencent": {
        "prefix": "careers.tencent.com/tencentcareer/api/post/Query*",
        "extract": lambda d: (d.get("Data") or {}).get("Posts") or [],
        "normalize": _normalize_tx,
    },
    "greenhouse": {
        "prefix": [f"boards-api.greenhouse.io/v1/boards/{b}/jobs?content=true*" for b in GH_BOARDS],
        "extract": lambda d: d.get("jobs") or [],
        "normalize": None,  # 按 board 分发，见 run_site
    },
}


def _fetch(url: str, timeout: int = 40, retries: int = 3) -> bytes:
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except Exception:  # noqa: BLE001 - archive.org 间歇超时，退避重试
            if i == retries - 1:
                raise
            time.sleep(8)
    raise RuntimeError("unreachable")


def list_snapshots(prefix: str | list[str], year_from: str, year_to: str) -> list[tuple[str, str]]:
    """CDX 枚举 [(timestamp, original_url)]，按时间升序（早->晚 append 保证首见=最早观测）。"""
    prefixes = prefix if isinstance(prefix, list) else [prefix]
    snaps: set[tuple[str, str]] = set()
    for p in prefixes:
        q = urllib.parse.urlencode(
            {
                "url": p,
                "output": "json",
                "from": year_from,
                "to": year_to,
                "filter": "statuscode:200",
                "limit": 5000,
            }
        )
        rows = json.loads(_fetch(f"{CDX}?{q}"))[1:]
        snaps |= {(r[1], r[2]) for r in rows}
        time.sleep(1.2)
    return sorted(snaps)


def run_site(site: str, year_from: str, year_to: str, max_snapshots: int) -> dict:
    cfg = SITES[site]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{site}.jsonl"
    seen_snapshots: set[str] = set()
    if out.is_file():  # 断点续跑：已处理的快照时间戳跳过
        for line in out.open(encoding="utf-8"):
            try:
                seen_snapshots.add(json.loads(line)["snapshot_ts"])
            except Exception:  # noqa: BLE001
                continue

    run = RunContext("jdarchive", {"cmd": "run", "site": site, "from": year_from, "to": year_to})
    snaps = list_snapshots(cfg["prefix"], year_from, year_to)
    todo = [(ts, url) for ts, url in snaps if ts not in seen_snapshots][:max_snapshots]
    run.log("jdarchive", site, "progress", count={"snapshots": len(snaps), "todo": len(todo)})

    fresh_records = 0
    t0 = time.monotonic()
    for i, (ts, orig) in enumerate(todo):
        try:
            body = _fetch(f"http://web.archive.org/web/{ts}id_/{orig}")
            try:
                text = gzip.decompress(body).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001 - 部分快照未压缩
                text = body.decode("utf-8", "replace")
            data = json.loads(text)
        except Exception as exc:  # noqa: BLE001 - 单快照失败不阻塞
            run.log("jdarchive", f"{site}:{ts[:8]}", "WARN", detail=str(exc)[:100])
            time.sleep(1.5)
            continue
        got = 0
        for post in cfg["extract"](data):
            if cfg["normalize"] is None:  # greenhouse：按 URL 里的 board 分发
                board = "gh"
                m = urllib.parse.urlparse(orig).path.split("/")
                if len(m) > 4:
                    board = m[4]
                rec = _normalize_gh(post, board)
            else:
                rec = cfg["normalize"](post, f"wb:{ts[:8]}")
            if rec:
                rec["snapshot_ts"] = ts  # 观测时间：jddiff 历史窗口的锚点
                with out.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                got += 1
        fresh_records += got
        if (i + 1) % 10 == 0 or (i + 1) == len(todo):
            elapsed = time.monotonic() - t0
            rate = (i + 1) / elapsed * 60
            eta = (len(todo) - i - 1) / max(rate, 0.01)
            run.log(
                "jdarchive",
                f"{site}:{i + 1}/{len(todo)}",
                "progress",
                count={"records": fresh_records, "per_min": round(rate, 1), "eta_min": round(eta)},
            )
        time.sleep(1.2)  # archive.org 限速 ~1 req/s

    metrics = {"snapshots_total": len(snaps), "snapshots_done": len(todo), "records": fresh_records}
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jdarchive")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--site", required=True, choices=sorted(SITES))
    p_run.add_argument("--from", dest="year_from", default="2022")
    p_run.add_argument("--to", dest="year_to", default="2026")
    p_run.add_argument("--max-snapshots", type=int, default=500)
    args = parser.parse_args(argv)
    result = run_site(args.site, args.year_from, args.year_to, args.max_snapshots)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
