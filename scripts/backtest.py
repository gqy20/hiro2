"""backtest: D8 滚动回测 CLI。

用法：
    uv run scripts/backtest.py run [--horizon 30] [--start 2025-09-01] [--end 2026-07-01]

每月 1 日为 as_of 点；对每个技能：
  预测 = 站在 as_of 用 momentum 规则外推方向（数据+词典双 as_of 闸门）
  实际 = [as_of, as_of+H) 对 [as_of-H, as_of) 的已实现方向
输出命中率、分方向指标与错误分类（data/processed/wechat-mp/backtest-h<H>.json）。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.skills.resolver import load_resolver, parse_day  # noqa: E402
from backend.temporal.features import build_series  # noqa: E402
from backend.temporal.forecast import forecast_skill, realized_direction  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "wechat-mp"


def month_starts(start: date, end: date) -> list[date]:
    out = []
    cur = date(start.year, start.month, 1)
    while cur <= end:
        out.append(cur)
        cur = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)
    return out


def cmd_run(horizon: int, start: date, end: date, data_end: date | None, rule: int = 1) -> dict:
    run = RunContext(
        "backtest",
        {"cmd": "run", "horizon": horizon, "start": str(start), "end": str(end), "rule": rule},
    )
    events = [
        e
        for e in (json.loads(x) for x in (PROCESSED / "events.jsonl").open(encoding="utf-8"))
        if e.get("is_primary", True)
    ]
    if data_end is None:
        days = sorted({(e.get("published_at") or "")[:10] for e in events if e.get("published_at")})
        data_end = parse_day(days[-1]) if days else end
        assert data_end is not None

    points = [t for t in month_starts(start, end) if t + timedelta(days=horizon) <= data_end]
    records, errors = [], Counter()
    flat_baseline_hits = 0
    comparable = 0
    resolver_full = load_resolver()  # 后验度量用全词典：未来实际发生的事按当时的词汇记录

    for as_of in points:
        resolver = load_resolver(as_of=as_of)  # 预测侧：词典时间闸门
        series_pred = build_series(events, resolver, as_of=as_of)  # 预测侧：数据时间闸门
        series_real = build_series(events, resolver_full, as_of=as_of + timedelta(days=horizon))
        for skill_id in sorted(set(series_pred) | set(series_real)):
            pred = forecast_skill(
                skill_id, series_pred.get(skill_id, []), as_of, horizon, rule=rule
            )
            if pred is None:
                continue
            actual = realized_direction(series_real.get(skill_id, []), as_of, horizon)
            if actual is None:
                continue
            comparable += 1
            hit = pred.direction == actual
            if actual == "flat":
                flat_baseline_hits += 1
            records.append(
                {
                    "as_of": str(as_of),
                    "skill_id": skill_id,
                    "predicted": pred.direction,
                    "actual": actual,
                    "hit": hit,
                    "confidence": pred.confidence,
                    "recent": pred.recent,
                    "prior": pred.prior,
                    "rule_version": rule,
                }
            )
            if not hit:
                errors[f"{pred.direction}->{actual}"] += 1

    hits = sum(1 for r in records if r["hit"])
    by_pred = Counter(r["predicted"] for r in records)
    by_actual = Counter(r["actual"] for r in records)
    metrics = {
        "horizon_days": horizon,
        "as_of_points": [str(p) for p in points],
        "predictions": len(records),
        "hits": hits,
        "accuracy": round(hits / len(records), 3) if records else None,
        "flat_baseline_accuracy": round(flat_baseline_hits / comparable, 3) if comparable else None,
        "by_predicted": dict(by_pred),
        "by_actual": dict(by_actual),
        "error_types": dict(errors),
        "rule_version": rule,
    }
    out_name = f"backtest-h{horizon}.json" if rule == 1 else f"backtest-h{horizon}-r{rule}.json"
    out = PROCESSED / out_name
    payload = {"metrics": metrics, "records": records}
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    run.log("backtest", "finished", "succeeded", count={"predictions": len(records)})
    run.finish({k: v for k, v in metrics.items() if not isinstance(v, list)})
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="backtest")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--horizon", type=int, default=30)
    p_run.add_argument("--start", type=str, default="2025-09-01")
    p_run.add_argument("--end", type=str, default="2026-07-01")
    p_run.add_argument("--rule", type=int, default=1, help="预测规则版本（forecast.py）")
    args = parser.parse_args(argv)

    start = parse_day(args.start)
    end = parse_day(args.end)
    assert start and end, "起止日期非法"
    metrics = cmd_run(args.horizon, start, end, None, rule=args.rule)
    print(
        json.dumps(
            {k: v for k, v in metrics.items() if k != "as_of_points"}, ensure_ascii=False, indent=1
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
