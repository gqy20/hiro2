"""jddiff: JD 技能两窗口 diff（主案例 2 的核心计算）。

用法：
    uv run scripts/jddiff.py run [--base 2026-03-01:2026-05-01] [--obs 2026-06-01:2026-08-01]

输入 jd-parsed.jsonl（is_ai_role、51job、带日期），按窗口聚合能力域提及份额，
输出新增/消失/增强/减弱四类变化及证据 JD。纯确定性计算，无 LLM。
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

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
CAPS = ROOT / "data" / "processed" / "capability-matrix" / "capabilities.json"
OUT = ROOT / "data" / "processed" / "jd-opencli" / "jd-diff.json"

MIN_MENTIONS = 2  # 窗口内低于此提及数不参与变化判定（噪声门）


def _parse_window(spec: str) -> tuple[date, date]:
    start_s, end_s = spec.split(":")
    return date.fromisoformat(start_s), date.fromisoformat(end_s)


def window_rows(rows: list[dict], start: date, end: date) -> list[dict]:
    return [
        r
        for r in rows
        if r.get("publish_date") and start.isoformat() <= r["publish_date"] < end.isoformat()
    ]


def window_caps(rows: list[dict]) -> Counter:
    """窗口内能力域提及计数（按 JD 解析的 resolved 归一结果）。"""
    c: Counter = Counter()
    for r in rows:
        for x in r.get("resolved") or []:
            c[x["skill_id"]] += 1
    return c


def cmd_run(base_spec: str, obs_spec: str) -> dict:
    run = RunContext("jddiff", {"cmd": "run", "base": base_spec, "obs": obs_spec})
    rows = [
        r
        for r in (json.loads(x) for x in PARSED.open(encoding="utf-8"))
        if r.get("is_ai_role") and r.get("platform") == "51job"
    ]
    base_w, obs_w = _parse_window(base_spec), _parse_window(obs_spec)
    base_rows = window_rows(rows, *base_w)
    obs_rows = window_rows(rows, *obs_w)
    base_c, obs_c = window_caps(base_rows), window_caps(obs_rows)
    base_total, obs_total = sum(base_c.values()), sum(obs_c.values())

    caps = {
        c["capability_id"]: c["name"]
        for c in json.loads(CAPS.read_text(encoding="utf-8"))["capabilities"]
    }
    # 证据索引：观察窗内含某能力域的 JD
    obs_evidence: dict[str, list[dict]] = defaultdict(list)
    for r in obs_rows:
        for sid in {x["skill_id"] for x in r.get("resolved") or []}:
            obs_evidence[sid].append(
                {"jd_id": r["jd_id"], "title": r["title"], "date": r["publish_date"]}
            )

    changes = []
    all_caps = set(base_c) | set(obs_c)
    for sid in sorted(all_caps):
        b, o = base_c.get(sid, 0), obs_c.get(sid, 0)
        bs, os_ = (b / base_total if base_total else 0), (o / obs_total if obs_total else 0)
        if b < MIN_MENTIONS and o < MIN_MENTIONS:
            continue
        if b < MIN_MENTIONS and o >= MIN_MENTIONS:
            ctype = "add"
        elif o < MIN_MENTIONS and b >= MIN_MENTIONS:
            ctype = "remove"
        elif bs > 0 and os_ / bs >= 1.5:
            ctype = "promote"
        elif os_ > 0 and os_ / bs <= 0.67:
            ctype = "demote"
        else:
            continue
        changes.append(
            {
                "capability_id": sid,
                "name": caps.get(sid, sid),
                "change_type": ctype,
                "base_mentions": b,
                "obs_mentions": o,
                "base_share": round(bs, 4),
                "obs_share": round(os_, 4),
                "evidence_jds": obs_evidence.get(sid, [])[:3],
            }
        )
    order = {"add": 0, "promote": 1, "demote": 2, "remove": 3}
    changes.sort(key=lambda c: (order[c["change_type"]], -c["obs_share"]))

    metrics = {
        "base_window": base_spec,
        "obs_window": obs_spec,
        "base_jds": len(base_rows),
        "obs_jds": len(obs_rows),
        "base_mentions": base_total,
        "obs_mentions": obs_total,
        "changes": len(changes),
        "by_type": dict(Counter(c["change_type"] for c in changes)),
    }
    payload = {"metrics": metrics, "changes": changes}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    run.log("jddiff", "finished", "succeeded", count=metrics)
    run.finish({k: v for k, v in metrics.items() if k != "by_type"})
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jddiff")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--base", default="2026-03-01:2026-05-01")
    p_run.add_argument("--obs", default="2026-06-01:2026-08-01")
    args = parser.parse_args(argv)
    result = cmd_run(args.base, args.obs)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
