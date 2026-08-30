"""predsnap: 预测快照——合并 ForecastEngine 预测 + leadtime 建议为文件快照。

用途（路线 A）：把时间情报域的预测产出固化为文件，供学练赛证"学"段挂钩，
  让匹配引擎（文件驱动、无 DB 依赖）能消费预测信号而不直连数据库。

数据链路：
  backtest-h{H}-r{rule}.json（最新 as_of 的各能力域预测方向+置信）
  + leadtime.json（信号领先 JD 的建议）
  -> data/processed/temporal/prediction-context.json（skill_id -> 预测上下文）

用法：
    uv run scripts/predsnap.py run [--horizon 30]

边界（docs/temporal-system.md）：快照只是预测信号的信息性反馈，
  不改变岗位版本、不绕过人工审核；学练段用它提示"是否值得现在学"。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
TEMPORAL_DIR = ROOT / "data" / "processed" / "wechat-mp"
OUT = ROOT / "data" / "processed" / "temporal" / "prediction-context.json"
CAPS = ROOT / "data" / "processed" / "capability-matrix" / "capabilities.json"

# 新涌现判定：基准窗信号量低于此值且近期有量（对齐 forecast.py 的 ratio=None 分支）
EMERGING_PRIOR = 1.0
RECENT_FLOOR = 2.0  # 对齐 forecast.py MIN_RECENT_WEIGHTED


def _cap_names() -> dict[str, str]:
    if not CAPS.is_file():
        return {}
    d = json.loads(CAPS.read_text(encoding="utf-8"))
    return {c["capability_id"]: c["name"] for c in d.get("capabilities", [])}


def _latest_forecasts(horizon: int) -> tuple[list[dict], str, int]:
    """取最新规则版本、最新 as_of 的预测记录。"""
    best_records, best_rule = [], 0
    for rule in (2, 1):
        path = TEMPORAL_DIR / f"backtest-h{horizon}-r{rule}.json"
        if path.is_file():
            best_records = json.loads(path.read_text(encoding="utf-8")).get("records", [])
            best_rule = rule
            break
    if not best_records:
        return [], "", best_rule
    latest_as_of = max(r["as_of"] for r in best_records)
    return [r for r in best_records if r["as_of"] == latest_as_of], latest_as_of, best_rule


def _suggestions() -> dict[str, dict]:
    lt_path = TEMPORAL_DIR / "leadtime.json"
    if not lt_path.is_file():
        return {}
    out: dict[str, dict] = {}
    for r in json.loads(lt_path.read_text(encoding="utf-8")).get("rows", []):
        out[r["capability_id"]] = {
            "change_type": "promote" if r.get("lead_days", 0) > 200 else "add",
            "lead_days": r.get("lead_days"),
            "reliability": r.get("reliability"),
        }
    return out


def cmd_run(horizon: int) -> dict:
    run = RunContext("predsnap", {"cmd": "run", "horizon": horizon})
    names = _cap_names()
    forecasts, as_of, rule = _latest_forecasts(horizon)
    suggestions = _suggestions()

    skills: dict[str, dict] = {}
    for r in forecasts:
        sid = r["skill_id"]
        recent = float(r.get("recent", 0))
        prior = float(r.get("prior", 0))
        direction = r.get("predicted", "flat")
        emerging = direction == "up" and prior < EMERGING_PRIOR and recent >= RECENT_FLOOR
        skills[sid] = {
            "name": names.get(sid, sid),
            "direction": direction,
            "confidence": float(r.get("confidence", 0)),
            "recent": recent,
            "prior": prior,
            "emerging": emerging,
            "suggestion": suggestions.get(sid),
        }

    payload = {
        "as_of": as_of,
        "horizon_days": horizon,
        "rule_version": rule,
        "generated_by": "predsnap.py（forecast backtest + leadtime 合并）",
        "skills": skills,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    up = sum(1 for s in skills.values() if s["direction"] == "up")
    em = sum(1 for s in skills.values() if s["emerging"])
    run.finish({"as_of": as_of, "skills": len(skills), "up": up, "emerging": em})
    return {"as_of": as_of, "rule": rule, "skills": len(skills), "up": up, "emerging": em}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="predsnap")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--horizon", type=int, default=30)
    args = parser.parse_args(argv)
    result = cmd_run(args.horizon)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
