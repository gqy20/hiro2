"""jobver: 岗位版本草稿与变更集组装（产品核心对象，contracts.md 语义）。

用法：
    uv run scripts/jobver.py run

产物：
  jobversion-agent-draft.json   主案例 1：AI Agent 工程师 JobVersion(DRAFT)
      —— Excel 专家基线为 v1，市场证据（56 条 JD + 日报信号）组装 v2 草稿，
         含逐能力 changeset（v1 评分 vs 市场份额）与证据引用
  jobchangeset-window-diff.json 主案例 2：两窗口 diff 归一为 JobChangeSet
      —— 变化项带证据 JD，供审核命令消费后创建新版本
全部确定性组装，status=DRAFT/PENDING，发布须经人工审核（产品规则）。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
ROLEMAP = ROOT / "data" / "processed" / "jd-opencli" / "jd-role-map.jsonl"
POSITIONS = ROOT / "data" / "processed" / "capability-matrix" / "positions.jsonl"
EMERGING = ROOT / "data" / "processed" / "jd-opencli" / "emerging-agent.json"
JDDIFF = ROOT / "data" / "processed" / "jd-opencli" / "jd-diff.json"
OUT_DRAFT = ROOT / "data" / "processed" / "jd-opencli" / "jobversion-agent-draft.json"
OUT_CS = ROOT / "data" / "processed" / "jd-opencli" / "jobchangeset-window-diff.json"

AGENT_TARGET = "AI Agent开发工程师"
# 变化判定用群内排名而非份额换算（份额与 Excel 0-5 评分不同量纲，直接换算不成立）


def cmd_run() -> dict:
    run = RunContext("jobver", {"cmd": "run"})
    positions = [json.loads(x) for x in POSITIONS.open(encoding="utf-8")]
    caps = {
        c["capability_id"]: c["name"]
        for c in json.loads(
            (ROOT / "data/processed/capability-matrix/capabilities.json").read_text(
                encoding="utf-8"
            )
        )["capabilities"]
    }
    parsed = {r["jd_id"]: r for r in (json.loads(x) for x in PARSED.open(encoding="utf-8"))}
    rolemap = [json.loads(x) for x in ROLEMAP.open(encoding="utf-8")]
    emerging = json.loads(EMERGING.read_text(encoding="utf-8"))

    agent_pos = next(p for p in positions if p["name"] == AGENT_TARGET)
    agent_jd_ids = [
        rm["jd_id"] for rm in rolemap if rm.get("position_id") == agent_pos["position_id"]
    ]

    # 市场侧能力分布（Agent 群）+ 每能力证据 JD
    market: Counter = Counter()
    points: Counter = Counter()
    evid: dict[str, list[str]] = {}
    for jid in agent_jd_ids:
        r = parsed[jid]
        for x in r.get("resolved") or []:
            sid = x["skill_id"]
            market[sid] += 1
            evid.setdefault(sid, []).append(jid)
            if x.get("point_id"):
                points[x["point_id"]] += 1
    total = sum(market.values()) or 1
    # 群内份额排名（跨量纲可比：不受绝对量影响）
    rank = {sid: i + 1 for i, (sid, _) in enumerate(market.most_common())}

    changeset = []
    for sid, n in market.most_common():
        share = n / total
        v1 = agent_pos["scores"].get(sid)
        if v1 is None:
            continue
        if v1 <= 2 and share >= 0.04:
            ctype = "add"  # 基线弱但市场成规模提及
        elif rank[sid] <= 3 and v1 <= 3:
            ctype = "promote"  # 市场前三但基线给分不高
        elif v1 >= 4 and share < 0.02:
            ctype = "demote"  # 基线高分但市场几乎不提
        else:
            continue
        changeset.append(
            {
                "level": "capability",
                "skill_id": sid,
                "name": caps.get(sid, sid),
                "change_type": ctype,
                "v1_score": v1,
                "market_share": round(share, 3),
                "market_rank": rank[sid],
                "evidence_jd_count": n,
                "evidence_jd_ids": evid[sid][:5],
            }
        )
    # 技能点级：市场证据揭示的细分点，Excel 基线只到能力域、无点级定义 -> add
    for pid, n in points.most_common(8):
        cap_id = pid.split(".")[0]
        changeset.append(
            {
                "level": "point",
                "skill_id": pid,
                "name": f"{caps.get(cap_id, cap_id)} · {pid.split('.', 1)[1]}",
                "change_type": "add",
                "v1_score": None,
                "market_share": round(n / total, 3),
                "market_rank": None,
                "evidence_jd_count": n,
                "note": "基线为能力域级评分，市场证据细化到技能点",
            }
        )

    draft = {
        "job_id": f"job_{agent_pos['position_id']}_agent",
        "version_id": "v2-draft-20260825",
        "status": "DRAFT",
        "title": "AI Agent 工程师",
        "basis": {
            "v1": f"Excel 专家基线（{agent_pos['position_id']} {AGENT_TARGET}）",
            "v2": "市场证据组装（56 条 JD 技能分布 + 日报信号先行）",
        },
        "required_skill_ids": [
            {"skill_id": sid, "name": caps.get(sid, sid), "weight": round(n / total, 3)}
            for sid, n in market.most_common(5)
        ],
        "preferred_skill_ids": [
            {"skill_id": sid, "name": caps.get(sid, sid), "weight": round(n / total, 3)}
            for sid, n in market.most_common(10)[5:]
        ],
        "valid_from": "2026-06-01",
        "evidence": {
            "jd_ids": agent_jd_ids,
            "jd_count": len(agent_jd_ids),
            "signal_total_weight": emerging["evidence"]["signal_precedence"]["signal_total_weight"],
            "emerging_ref": str(EMERGING.relative_to(ROOT)),
        },
        "changeset_vs_v1": changeset,
        "review_status": "PENDING",
        "generated_by": "jobver v1（确定性组装）",
        "generated_at": date.today().isoformat(),
    }
    OUT_DRAFT.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    # 主案例 2：两窗口 diff -> JobChangeSet
    diff = json.loads(JDDIFF.read_text(encoding="utf-8"))
    changeset2 = [
        {
            "skill_id": c["capability_id"],
            "name": c["name"],
            "change_type": c["change_type"],
            "base_share": c["base_share"],
            "obs_share": c["obs_share"],
            "base_mentions": c["base_mentions"],
            "obs_mentions": c["obs_mentions"],
            "evidence_jds": c["evidence_jds"],
        }
        for c in diff["changes"]
    ]
    cs = {
        "changeset_id": "cs_window_diff_20260304_20260607",
        "job_scope": "AI 域综合（51job、AI 判定、带日期）",
        "base_window": diff["metrics"]["base_window"],
        "obs_window": diff["metrics"]["obs_window"],
        "sample": {
            "base_jds": diff["metrics"]["base_jds"],
            "obs_jds": diff["metrics"]["obs_jds"],
            "note": "基准窗样本受平台在招职位时效限制，结论为方向性",
        },
        "changes": changeset2,
        "review_status": "PENDING",
        "generated_by": "jobver v1（确定性组装，源自 jddiff）",
    }
    OUT_CS.write_text(json.dumps(cs, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = {
        "draft_changes": len(changeset),
        "changeset2_changes": len(changeset2),
        "agent_jds": len(agent_jd_ids),
    }
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobver")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    args = parser.parse_args(argv)
    print(json.dumps(cmd_run(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
