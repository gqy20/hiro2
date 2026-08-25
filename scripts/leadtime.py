"""leadtime: 日报信号领先 JD 需求的提前量验证（事件研究法）。

用法：
    uv run scripts/leadtime.py run

对每个能力域（两侧样本量足够者）：
  信号启动月 = 日报月度加权提及首次 >= SIGNAL_ONSET 且此后累计达总量 50%
  需求落地月 = JD（51job、带日期、AI 域）月度提及首次 >= JD_ONSET
  提前天数   = 落地月初 - 启动月初（月粒度，注明）
两侧同用当前词典度量（描述性对比，非预测回测；该口径差在报告 limitation 注明）。
输出 data/processed/wechat-mp/leadtime.json 与终端摘要。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.skills.resolver import load_resolver  # noqa: E402
from backend.temporal.features import FACT_WEIGHTS  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "data" / "processed" / "wechat-mp" / "events.jsonl"
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
CAPS = ROOT / "data" / "processed" / "capability-matrix" / "capabilities.json"
OUT = ROOT / "data" / "processed" / "wechat-mp" / "leadtime.json"

SIGNAL_ONSET = 3.0  # 日报月度加权提及阈值
SUSTAIN_RATIO = 0.5  # 启动后须累计到总量的该比例（防单月毛刺）
JD_ONSET = 2  # JD 月度提及阈值
MIN_SIGNAL_TOTAL = 15.0
MIN_JD_TOTAL = 4


def month_key(day: str) -> str:
    return day[:7]


def month_start(ym: str) -> date:
    return date(int(ym[:4]), int(ym[5:7]), 1)


def build_signal_months() -> dict[str, Counter]:
    resolver = load_resolver()
    sig: dict[str, Counter] = defaultdict(Counter)
    for line in EVENTS.open(encoding="utf-8"):
        e = json.loads(line)
        if not e.get("is_primary", True):
            continue
        day = (e.get("published_at") or "")[:10]
        if not day:
            continue
        w = FACT_WEIGHTS.get(e.get("fact_grade", "report"), 0.6)
        for m in e.get("skill_mentions") or []:
            hit = resolver.resolve(m)
            if hit.skill_id:
                sig[hit.skill_id][month_key(day)] += w
    return sig


def build_jd_months() -> dict[str, Counter]:
    jd: dict[str, Counter] = defaultdict(Counter)
    for line in PARSED.open(encoding="utf-8"):
        r = json.loads(line)
        if not r.get("is_ai_role") or r.get("platform") != "51job":
            continue
        day = r.get("publish_date") or ""
        if not day:
            continue
        for x in r.get("resolved") or []:
            jd[x["skill_id"]][month_key(day)] += 1
    return jd


def onset_month(series: Counter, threshold: float, sustain_ratio: float) -> str | None:
    """首次达阈值、且其后（含当月）累计达总量 sustain_ratio 的月份。"""
    total = sum(series.values())
    if total <= 0:
        return None
    months = sorted(series)
    for i, ym in enumerate(months):
        if series[ym] >= threshold and sum(series[m] for m in months[i:]) >= total * sustain_ratio:
            return ym
    return None


def cmd_run() -> dict:
    run = RunContext("leadtime", {"cmd": "run"})
    sig = build_signal_months()
    jds = build_jd_months()
    caps = {
        c["capability_id"]: c["name"]
        for c in json.loads(CAPS.read_text(encoding="utf-8"))["capabilities"]
    }

    # JD 观测窗起点：信号启动早于它的能力，提前量含左删失成分（下界）
    jd_window_start = min((m for c in jds.values() for m in c), default=None)

    rows = []
    for sid in sorted(set(sig) | set(jds)):
        s_total, j_total = sum(sig[sid].values()), sum(jds[sid].values())
        if s_total < MIN_SIGNAL_TOTAL or j_total < MIN_JD_TOTAL:
            continue
        s_onset = onset_month(sig[sid], SIGNAL_ONSET, SUSTAIN_RATIO)
        j_onset = onset_month(jds[sid], JD_ONSET, 0.5)
        if not s_onset or not j_onset:
            continue
        lead = (month_start(j_onset) - month_start(s_onset)).days
        # 可信度：clean = 信号启动在 JD 观测窗内，全程可验证；
        # lower_bound = 信号早于观测窗，真实提前量 >= 观测窗内部分
        if s_onset >= (jd_window_start or "9999-99"):
            reliability = "clean"
        elif j_onset >= (jd_window_start or "9999-99"):
            reliability = "lower_bound"
        else:
            reliability = "invalid"
        rows.append(
            {
                "capability_id": sid,
                "name": caps.get(sid, sid),
                "signal_onset": s_onset,
                "jd_onset": j_onset,
                "lead_days": lead,
                "reliability": reliability,
                "signal_total": round(s_total, 1),
                "jd_total": j_total,
                "jd_peak_month": jds[sid].most_common(1)[0][0],
            }
        )
    rows.sort(key=lambda r: -r["lead_days"])
    led = [r for r in rows if r["lead_days"] > 30]
    OUT.write_text(
        json.dumps(
            {
                "rows": rows,
                "params": {
                    "signal_onset": SIGNAL_ONSET,
                    "jd_onset": JD_ONSET,
                    "granularity": "月",
                    "dictionary": "两侧同用当前全词典（描述性口径）",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    clean = [r for r in rows if r["reliability"] == "clean" and r["lead_days"] > 30]
    metrics = {
        "capabilities": len(rows),
        "signal_leads_jd_over_30d": len(led),
        "clean_leads_over_30d": len(clean),
        "jd_window_start": jd_window_start,
        "median_lead_days": sorted(r["lead_days"] for r in rows)[len(rows) // 2] if rows else None,
    }
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="leadtime")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    parser.parse_args(argv)
    result = cmd_run()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
