"""livcast: 实时预测（路线 B）——用最新信号生成当前趋势预测。

与 backtest 的区别：
  backtest = 站在历史 as_of 点，数据+词典双闸门，对比已实现方向（评估用）。
  livcast  = 站在最新数据日，无时间闸门（全量数据 + 全词典），只向前预测（生产用）。

数据链路（对齐 temporal-system.md"未来预测"模式）：
  当前事件（events.jsonl, is_primary）-> build_series(全词典, as_of=数据末日)
  -> forecast_skill（rule v2）-> data/processed/temporal/live-forecast.json

用法：
    uv run scripts/livcast.py run [--horizon 30]

产物供 predsnap.py --source live 消费，最终挂到学练段前瞻提示。
边界：预测只生成信号，不改岗位版本、不绕过人工审核。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

from backend.skills.resolver import load_resolver, parse_day  # noqa: E402
from backend.temporal.features import build_series  # noqa: E402
from backend.temporal.forecast import RULE_VERSION, forecast_skill  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "data" / "processed" / "wechat-mp" / "events.jsonl"
OUT = ROOT / "data" / "processed" / "temporal" / "live-forecast.json"


def cmd_run(horizon: int) -> dict:
    run = RunContext("livcast", {"cmd": "run", "horizon": horizon, "rule": RULE_VERSION})
    events = [
        e
        for e in (json.loads(x) for x in EVENTS.open(encoding="utf-8"))
        if e.get("is_primary", True)
    ]
    days = sorted({(e.get("published_at") or "")[:10] for e in events if e.get("published_at")})
    if not days:
        run.finish({"error": "no events"}, status="FAILED")
        return {"error": "no events"}
    as_of = parse_day(days[-1])  # 最新数据日作为 live 预测基准
    assert as_of is not None

    resolver = load_resolver()  # live 用全词典（站在当下，无回望偏差）
    series = build_series(events, resolver, as_of=as_of)  # as_of 之后的数据不纳入

    records = []
    for skill_id in sorted(series):
        pred = forecast_skill(skill_id, series[skill_id], as_of, horizon, rule=RULE_VERSION)
        if pred is None:
            continue
        records.append(
            {
                "as_of": str(as_of),
                "skill_id": skill_id,
                "predicted": pred.direction,
                "confidence": pred.confidence,
                "recent": pred.recent,
                "prior": pred.prior,
                "rule_version": RULE_VERSION,
            }
        )

    payload = {
        "mode": "live",
        "as_of": str(as_of),
        "horizon_days": horizon,
        "rule_version": RULE_VERSION,
        "records": records,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    up = sum(1 for r in records if r["predicted"] == "up")
    down = sum(1 for r in records if r["predicted"] == "down")
    run.finish({"as_of": str(as_of), "skills": len(records), "up": up, "down": down})
    return {"as_of": str(as_of), "skills": len(records), "up": up, "down": down}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="livcast")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--horizon", type=int, default=30)
    args = parser.parse_args(argv)
    result = cmd_run(args.horizon)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
