"""jdasof: JD 历史解析的词典回望修复——按各 JD 发布日 as_of 重算技能归一。

问题：jd-parsed.jsonl 的历史 JD（Wayback 2018-2022 等）用当前词典解析，
SKILLS-EARNED v4 的 2026-08 习得词被用于 2021 年 JD（回望偏差），四侧对比
AI 域 onset 被虚增（详 roadmap D6 混杂标注）。
做法：skill_mentions 原词不变，仅按 publish_date 当天的词典状态重算 resolved，
写 jd-parsed-asof.jsonl（不覆盖原文件），输出前后命中差统计。
用法：uv run scripts/jdasof.py run
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.skills.resolver import load_resolver  # noqa: E402

SRC = Path("data/processed/jd-opencli/jd-parsed.jsonl")
OUT = Path("data/processed/jd-opencli/jd-parsed-asof.jsonl")


def _as_of(day: str) -> date:
    return date(int(day[:4]), int(day[5:7]), int(day[8:10]))


def cmd_run() -> dict:
    run = RunContext("jdasof", {"cmd": "run"})
    resolvers: dict[str, object] = {}
    n = old_hits = new_hits = 0
    # 历史窗（<2024-01）的 AI 域命中变化是回望偏差的直接量度
    ai_caps = {"cap_01", "cap_03", "cap_04", "cap_05", "cap_06"}
    old_ai_hist = new_ai_hist = 0

    with OUT.open("w", encoding="utf-8") as out:
        for line in SRC.open(encoding="utf-8"):
            r = json.loads(line)
            day = r.get("publish_date") or ""
            if day and len(day) >= 10:
                key = day[:10]
                if key not in resolvers:
                    resolvers[key] = load_resolver(as_of=_as_of(key))
                resolver = resolvers[key]
            else:
                resolver = resolvers.get("", None) or load_resolver()
                resolvers[""] = resolver

            old = r.get("resolved") or []
            new = []
            for m in r.get("skill_mentions") or []:
                hit = resolver.resolve(m)
                if hit.skill_id:
                    new.append(
                        {"mention": m, "skill_id": hit.skill_id, "point_id": hit.point_id}
                    )
            r["resolved"] = new
            r["asof_rule_version"] = f"skills-asof-{day[:10]}"
            out.write(json.dumps(r, ensure_ascii=False) + "\n")

            n += 1
            old_hits += len(old)
            new_hits += len(new)
            hist = bool(day) and day < "2024-01-01"
            if hist:
                old_ai_hist += sum(1 for x in old if x["skill_id"] in ai_caps)
                new_ai_hist += sum(1 for x in new if x["skill_id"] in ai_caps)

    metrics = {
        "records": n,
        "resolver_versions": len(resolvers),
        "old_hits": old_hits,
        "new_hits": new_hits,
        "old_ai_hits_pre2024": old_ai_hist,
        "new_ai_hits_pre2024": new_ai_hist,
        "lookahead_removed": old_hits - new_hits,
        "lookahead_ai_pre2024_removed": old_ai_hist - new_ai_hist,
    }
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jdasof")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    parser.parse_args(argv)
    print(json.dumps(cmd_run(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
