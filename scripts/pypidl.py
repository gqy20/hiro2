"""pypidl: PyPI/npm 技术信号 -> 能力域，与日报/JD leadtime 同口径对比。

用法：
    uv run scripts/pypidl.py fetch   # 拉 pypistats.org 近 180 天日下载（短窗参考，不作历史源）
    uv run scripts/pypidl.py rels    # 拉 pypi.org JSON API 全版本发布时间线（萌芽锚点）
    uv run scripts/pypidl.py ch      # ClickHouse Linehaul 月度聚合 2016 起全历史（主通路）
    uv run scripts/pypidl.py hist    # BigQuery 同口径备份通路（额度受限时用 ch）
    uv run scripts/pypidl.py npm     # npm downloads API 2015 起月度下载（独立生态对照）
    uv run scripts/pypidl.py pepy    # pepy.tech 近 90 天月度下载（滚动自建历史，key 在 .env）
    uv run scripts/pypidl.py run     # 下载份额 onset + 首发月 + 日报/JD 对比

通路实测（2026-08-28）：pypistats 全端点仅 180 天；GitHub stargazers 端点 2026-06-30 起仅限
仓库管理员；PyPI 下载历史唯一无 key 通路 = BigQuery 公共数据集（实测 2018 起全历史扫描
324GB，免费额度 1TB/月内；扫描量只随月数增长、与包数无关）；npm range API 全历史分段可拉。
信号口径与 limitation 见 data/PKGS.yml 头注。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

import yaml  # noqa: E402
from leadtime import (  # noqa: E402
    build_jd_months,
    build_signal_months,
    month_start,
    onset_month,
)
from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PKGS = ROOT / "data" / "PKGS.yml"
RAW_DIR = ROOT / "data" / "raw" / "pypi"
HIST = RAW_DIR / "dlhist.csv"
NPMHIST = RAW_DIR / "npmhist.csv"
PEPYHIST = RAW_DIR / "pepyhist.csv"
OUT = ROOT / "data" / "processed" / "pypi" / "relsignal.json"

API = "https://pypistats.org/api/packages/{pkg}/overall"
PYPI_JSON = "https://pypi.org/pypi/{pkg}/json"
NPM_API = "https://api.npmjs.org/downloads/range/{start}:{end}/{pkg}"
PEPY_API = "https://api.pepy.tech/api/v2/projects/{pkg}"
SLEEP = 1.2  # pypistats 限速约 1 req/s
BQ_SINCE = "2018-01-01"


def _pepy_key() -> str:
    """从 .env 读 PEPY_API_KEY（无 dotenv 依赖的简易解析）。"""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            if line.startswith("PEPY_API_KEY="):
                return line.split("=", 1)[1].strip()
    return os.environ.get("PEPY_API_KEY", "")


def load_pkgs() -> tuple[list[dict], dict]:
    cfg = yaml.safe_load(PKGS.read_text(encoding="utf-8"))
    return cfg["packages"], cfg


def _get(url: str, headers: dict | None = None) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "hiro2-research/0.1", **(headers or {})}
    )
    return urllib.request.urlopen(req, timeout=30).read()


def cmd_fetch() -> dict:
    run = RunContext("pypidl", {"cmd": "fetch", "api": "pypistats.org/overall"})
    pkgs, _ = load_pkgs()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ok = skip = fail = 0
    for item in pkgs:
        pkg = item["pkg"]
        dest = RAW_DIR / f"{pkg}.json"
        if dest.exists():
            skip += 1
            continue
        try:
            dest.write_bytes(_get(API.format(pkg=pkg)))
            ok += 1
        except Exception as exc:  # noqa: BLE001 - 单包失败进隔离清单，不中断批量
            print(f"WARN {pkg}: {exc}", file=sys.stderr)
            fail += 1
        time.sleep(SLEEP)
    hashes = {
        f.name: hashlib.sha256(f.read_bytes()).hexdigest()[:16]
        for f in sorted(RAW_DIR.glob("*.json"))
        if f.name != "manifest.json"
    }
    (RAW_DIR / "manifest.json").write_text(
        json.dumps(
            {"fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "sha256_16": hashes},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    metrics = {"ok": ok, "skip": skip, "fail": fail, "total": len(pkgs)}
    run.finish(metrics)
    return metrics


def cmd_rels() -> dict:
    """拉各包全版本发布时间线（pypi.org JSON API，无 key），瘦身为 version -> upload_time。"""
    run = RunContext("pypidl", {"cmd": "rels", "api": "pypi.org/pypi/{pkg}/json"})
    pkgs, _ = load_pkgs()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ok = skip = fail = 0
    for item in pkgs:
        pkg = item["pkg"]
        dest = RAW_DIR / f"{pkg}-rels.json"
        if dest.exists():
            skip += 1
            continue
        try:
            data = json.loads(_get(PYPI_JSON.format(pkg=pkg)))
            releases = {}
            for ver, files in (data.get("releases") or {}).items():
                times = sorted(f.get("upload_time") for f in files if f.get("upload_time"))
                if times:
                    releases[ver] = times[0]
            dest.write_text(
                json.dumps(
                    {
                        "pkg": pkg,
                        "first_release": min(releases.values()) if releases else None,
                        "releases": releases,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            ok += 1
        except Exception as exc:  # noqa: BLE001 - 单包失败进清单不中断
            print(f"WARN {pkg}: {exc}", file=sys.stderr)
            fail += 1
        time.sleep(0.4)
    metrics = {"ok": ok, "skip": skip, "fail": fail, "total": len(pkgs)}
    run.finish(metrics)
    return metrics


CH_URL = "https://sql-clickhouse.clickhouse.com?user=demo&default_format=JSON"


def cmd_ch() -> dict:
    """ClickHouse 官方 Playground 的 pypi.pypi_downloads_per_month（Linehaul 同源
    月度聚合，2016-01 起全覆盖；demo 免费且为聚合表轻查询）——绕开 BigQuery 额度，
    口径已交叉验证（torch 2018-01=9502 与 BigQuery 逐位一致），写同格式 dlhist.csv。
    """
    run = RunContext("pypidl", {"cmd": "ch", "api": "sql-clickhouse.clickhouse.com"})
    pkgs, _ = load_pkgs()
    names = ", ".join(f"'{p['pkg']}'" for p in pkgs)
    sql = (
        "SELECT month, project, SUM(count) AS dl FROM pypi.pypi_downloads_per_month "
        f"WHERE project IN ({names}) GROUP BY month, project ORDER BY month, project"
    )
    req = urllib.request.Request(
        CH_URL,
        data=sql.encode("utf-8"),
        method="POST",
        headers={"User-Agent": "hiro2-research/0.1"},
    )
    data = json.loads(urllib.request.urlopen(req, timeout=300).read())
    lines = [f"{r['month'][:7]},{r['project']},{int(r['dl'])}" for r in data["data"]]
    HIST.write_text("ym,pkg,downloads\n" + "\n".join(lines) + "\n", encoding="utf-8")
    metrics = {
        "rows": len(lines),
        "months": len({ln.split(",")[0] for ln in lines}),
        "pkgs_seen": len({ln.split(",")[1] for ln in lines}),
        "pkgs_expected": len(pkgs),
    }
    run.finish(metrics)
    return metrics


def cmd_hist() -> dict:
    """BigQuery Linehaul 月度下载：全部包一次查询（扫描量只随月数增长，与包数无关）。"""
    bq = shutil.which("bq") or str(Path.home() / "tools/google-cloud-sdk/bin/bq")
    if not Path(bq).exists():
        print("ERROR: bq not found（gcloud CLI 未安装或未在 PATH）", file=sys.stderr)
        return {"error": "bq_not_found"}
    pkgs, _ = load_pkgs()
    names = ", ".join(f'"{p["pkg"]}"' for p in pkgs)
    sql = (
        'SELECT FORMAT_TIMESTAMP("%Y-%m", timestamp) AS ym, file.project AS pkg, '
        "COUNT(*) AS downloads "
        "FROM `bigquery-public-data.pypi.file_downloads` "
        f'WHERE timestamp >= TIMESTAMP("{BQ_SINCE}") AND file.project IN ({names}) '
        "GROUP BY ym, pkg ORDER BY ym, pkg"
    )
    run = RunContext("pypidl", {"cmd": "hist", "since": BQ_SINCE, "pkgs": len(pkgs)})
    proc = subprocess.run(
        [bq, "query", "--use_legacy_sql=false", "--format=csv", "--max_rows=200000", sql],
        capture_output=True,
        text=True,
        timeout=1800,
    )
    if proc.returncode != 0:
        print(f"ERROR bq stderr: {proc.stderr[-300:]}", file=sys.stderr)
        print(f"ERROR bq stdout: {proc.stdout[-500:]}", file=sys.stderr)
        return {"error": "bq_failed"}
    rows = list(csv.DictReader(io.StringIO(proc.stdout)))
    HIST.write_text(proc.stdout, encoding="utf-8")
    metrics = {
        "rows": len(rows),
        "months": len({r["ym"] for r in rows}),
        "pkgs_seen": len({r["pkg"] for r in rows}),
        "pkgs_expected": len(pkgs),
    }
    run.finish(metrics)
    return metrics


def build_dl_hist() -> dict[str, Counter]:
    """dlhist.csv -> 域月度下载序列（域内求和）。"""
    return _hist_by_cap(HIST, "packages")


def build_npm_hist() -> dict[str, Counter]:
    """npmhist.csv -> 域月度下载序列（npm 生态，独立分母）。"""
    return _hist_by_cap(NPMHIST, "npm_packages")


def _hist_by_cap(path: Path, section: str) -> dict[str, Counter]:
    _, cfg = load_pkgs()
    cap_of = {p["pkg"]: p["cap"] for p in (cfg.get(section) or [])}
    series: dict[str, Counter] = defaultdict(Counter)
    if not path.exists():
        return series
    for r in csv.DictReader(path.open(encoding="utf-8")):
        cap = cap_of.get(r["pkg"])
        if cap:
            series[cap][r["ym"]] += int(r["downloads"])
    return series


def _npm_segments() -> list[tuple[str, str]]:
    """range API 上限 18 个月/次，从 2015-01 起分段覆盖至今。"""
    segs: list[tuple[str, str]] = []
    cur = date(2015, 1, 1)
    today = date.today()
    while cur < today:
        m = cur.month - 1 + 18
        nxt = date(cur.year + m // 12, m % 12 + 1, 1)
        segs.append((cur.isoformat(), min(nxt, today).isoformat()))
        cur = nxt
    return segs


def _npm_get_json(url: str) -> dict:
    """带 429 退避的 GET（npm 限速窗口严格，突发会被熔断）。"""
    for wait in (0, 15, 45, 120):
        if wait:
            time.sleep(wait)
        try:
            return json.loads(_get(url))
        except urllib.error.HTTPError as he:
            if he.code == 429 and wait < 120:
                continue
            raise
    raise RuntimeError("npm rate limit retries exhausted")


def cmd_npm() -> dict:
    """npm 月度下载：逐包分段拉 range API（无 key），聚合计数写 npmhist.csv。

    段级 404 容忍：新包对早期段不存在（range API 返回 404），跳段不弃包。
    """
    run = RunContext("pypidl", {"cmd": "npm", "api": "npmjs.org/downloads/range"})
    _, cfg = load_pkgs()
    pkgs = cfg.get("npm_packages") or []
    lines: list[str] = []
    ok = fail = seg404 = 0
    for item in pkgs:
        pkg = item["pkg"]
        got_any = False
        try:
            for start, end in _npm_segments():
                time.sleep(0.6)
                url = NPM_API.format(start=start, end=end, pkg=urllib.parse.quote(pkg, safe="@"))
                try:
                    data = _npm_get_json(url)
                except urllib.error.HTTPError as he:
                    if he.code == 404:
                        seg404 += 1
                        continue
                    raise
                monthly: Counter = Counter()
                for d in data.get("downloads") or []:
                    monthly[str(d["day"])[:7]] += int(d["downloads"])
                lines += [f"{ym},{pkg},{v}" for ym, v in sorted(monthly.items()) if v > 0]
                got_any = True
            if got_any:
                ok += 1
            else:
                print(f"WARN npm {pkg}: no data in any segment", file=sys.stderr)
                fail += 1
        except Exception as exc:  # noqa: BLE001 - 单包失败进清单不中断
            print(f"WARN npm {pkg}: {exc}", file=sys.stderr)
            fail += 1
    NPMHIST.write_text("ym,pkg,downloads\n" + "\n".join(lines) + "\n", encoding="utf-8")
    months = {ln.split(",")[0] for ln in lines}
    metrics = {
        "ok": ok,
        "fail": fail,
        "total": len(pkgs),
        "months": len(months),
        "rows": len(lines),
        "seg_404_skipped": seg404,
    }
    run.finish(metrics)
    return metrics


def cmd_pepy() -> dict:
    """pepy.tech 近 90 天下载（免费档窗口），月度聚合滚动追加 pepyhist.csv。

    每月跑一次即自建下载历史；回溯历史仍走 BigQuery（hist）。
    """
    key = _pepy_key()
    if not key:
        print("ERROR: PEPY_API_KEY 未配置（.env）", file=sys.stderr)
        return {"error": "no_key"}
    run = RunContext("pypidl", {"cmd": "pepy", "api": "pepy.tech/api/v2"})
    pkgs, _ = load_pkgs()
    lines: list[str] = []
    ok = fail = 0
    for item in pkgs:
        pkg = item["pkg"]
        try:
            data = None
            for wait in (0, 20, 60):
                if wait:
                    time.sleep(wait)
                try:
                    data = json.loads(_get(PEPY_API.format(pkg=pkg), headers={"X-Api-Key": key}))
                    break
                except urllib.error.HTTPError as he:
                    if he.code == 429 and wait < 60:
                        continue
                    raise
            monthly: Counter = Counter()
            for day, n in (data.get("downloads") or {}).items():
                # 部分包返回嵌套 {date: {with_mirrors: x, ...}}，取全量和
                if isinstance(n, dict):
                    n = sum(v for v in n.values() if isinstance(v, (int, float)))
                monthly[str(day)[:7]] += int(n)
            lines += [f"{ym},{pkg},{v}" for ym, v in sorted(monthly.items()) if v > 0]
            ok += 1
        except Exception as exc:  # noqa: BLE001 - 单包失败进清单不中断
            print(f"WARN pepy {pkg}: {exc}", file=sys.stderr)
            fail += 1
        time.sleep(2.0)
    # 滚动合并：旧月份保留，新月份覆盖（同 ym+pkg 去重取新）
    seen: dict[tuple[str, str], str] = {}
    if PEPYHIST.exists():
        for r in csv.DictReader(PEPYHIST.open(encoding="utf-8")):
            seen[(r["ym"], r["pkg"])] = r["downloads"]
    for ln in lines:
        ym, pkg, v = ln.split(",")
        seen[(ym, pkg)] = v
    body = "ym,pkg,downloads\n" + "".join(
        f"{ym},{pkg},{v}\n" for (ym, pkg), v in sorted(seen.items())
    )
    PEPYHIST.write_text(body, encoding="utf-8")
    months = {k[0] for k in seen}
    metrics = {
        "ok": ok,
        "fail": fail,
        "total": len(pkgs),
        "months_cumulative": len(months),
        "rows": len(seen),
    }
    run.finish(metrics)
    return metrics


def build_rel_months() -> tuple[dict[str, Counter], dict[str, dict]]:
    """逐包月度 release 计数 -> 域月度序列与逐包元数据（首发时间/版本数）。"""
    pkgs, _ = load_pkgs()
    cap_series: dict[str, Counter] = defaultdict(Counter)
    pkg_meta: dict[str, dict] = {}
    for item in pkgs:
        f = RAW_DIR / f"{item['pkg']}-rels.json"
        if not f.exists():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        times = list((data.get("releases") or {}).values())
        s = Counter(t[:7] for t in times)
        cap_series[item["cap"]].update(s)
        pkg_meta[item["pkg"]] = {
            "first_release": data.get("first_release"),
            "versions": len(times),
        }
    return cap_series, pkg_meta


def median(values: list):
    s = sorted(values)
    return s[len(s) // 2] if s else None


def cmd_run() -> dict:
    pkgs, cfg = load_pkgs()
    dl = build_dl_hist()
    npm = build_npm_hist()
    cap_series, pkg_meta = build_rel_months()
    jds = build_jd_months()
    sig = build_signal_months()
    cap_of = {item["pkg"]: item["cap"] for item in pkgs}
    share_onset, sustain = cfg.get("share_onset", 0.02), cfg.get("sustain", 0.30)

    # 下载份额：当月该域 / 当月同生态受监控包总量，按月归一对消生态级通胀；npm 独立分母
    def _shares(series: dict[str, Counter]) -> dict[str, Counter]:
        totals: Counter = Counter()
        for s in series.values():
            totals.update(s)
        return {
            cap: Counter({m: v / totals[m] for m, v in s.items() if totals.get(m, 0) > 0})
            for cap, s in series.items()
        }

    shares, npm_shares = _shares(dl), _shares(npm)

    run = RunContext(
        "pypidl",
        {
            "cmd": "run",
            "share_onset": share_onset,
            "sustain": sustain,
            "dl_hist": HIST.exists(),
            "npm_hist": NPMHIST.exists(),
        },
    )
    rows = []
    for cap in sorted(set(dl) | set(npm) | set(cap_series)):
        dl_onset = onset_month(shares[cap], share_onset, sustain) if shares.get(cap) else None
        npm_onset = (
            onset_month(npm_shares[cap], share_onset, sustain) if npm_shares.get(cap) else None
        )
        firsts = [
            m["first_release"][:7]
            for p, m in pkg_meta.items()
            if cap_of[p] == cap and m["first_release"]
        ]
        rel_onset = median(firsts)
        jd_onset = onset_month(jds[cap], 2, 0.5) if sum(jds[cap].values()) >= 4 else None
        rp_onset = onset_month(sig[cap], 3.0, 0.5) if sum(sig[cap].values()) >= 15 else None
        rows.append(
            {
                "capability_id": cap,
                "dl_share_onset": dl_onset,
                "npm_share_onset": npm_onset,
                "rel_onset": rel_onset,
                "jd_onset": jd_onset,
                "report_onset": rp_onset,
                "dl_leads_jd_days": (
                    (month_start(jd_onset) - month_start(dl_onset)).days
                    if dl_onset and jd_onset
                    else None
                ),
                "npm_leads_jd_days": (
                    (month_start(jd_onset) - month_start(npm_onset)).days
                    if npm_onset and jd_onset
                    else None
                ),
                "rel_leads_jd_days": (
                    (month_start(jd_onset) - month_start(rel_onset)).days
                    if rel_onset and jd_onset
                    else None
                ),
                "report_leads_jd_days": (
                    (month_start(jd_onset) - month_start(rp_onset)).days
                    if rp_onset and jd_onset
                    else None
                ),
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "rows": rows,
                "pkg_meta": pkg_meta,
                "params": {
                    "dl_share_onset": share_onset,
                    "sustain": sustain,
                    "granularity": "月",
                    "note": "dl_share = 下载份额启动（量级信号）；rel = 首发月中位（萌芽锚点）",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    def _med(key: str):
        vs = [r[key] for r in rows if r[key] is not None]
        return median(vs)

    metrics = {
        "capabilities": len(rows),
        "dl_leads_jd_median_days": _med("dl_leads_jd_days"),
        "npm_leads_jd_median_days": _med("npm_leads_jd_days"),
        "rel_leads_jd_median_days": _med("rel_leads_jd_days"),
        "report_leads_jd_median_days": _med("report_leads_jd_days"),
        "pkgs": len(pkg_meta),
        "dl_hist": HIST.exists(),
        "npm_hist": NPMHIST.exists(),
    }
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pypidl")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    sub.add_parser("rels")
    sub.add_parser("ch")
    sub.add_parser("hist")
    sub.add_parser("npm")
    sub.add_parser("pepy")
    sub.add_parser("run")
    args = parser.parse_args(argv)
    result = {
        "fetch": cmd_fetch,
        "rels": cmd_rels,
        "ch": cmd_ch,
        "hist": cmd_hist,
        "npm": cmd_npm,
        "pepy": cmd_pepy,
        "run": cmd_run,
    }[args.cmd]()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
