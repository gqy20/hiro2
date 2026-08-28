"""jobver: 岗位版本草稿与变更集组装（产品核心对象，contracts.md 语义）。

用法：
    uv run scripts/jobver.py run                        # AI Agent 主案例（1+2）
    uv run scripts/jobver.py run --job pos_01 --slug llm-algo   # 任意岗位 v2 草稿

产物：
  jobversion-agent-draft.json   主案例 1：AI Agent 工程师 JobVersion(DRAFT)
      —— Excel 专家基线为 v1，市场证据（56 条 JD + 日报信号）组装 v2 草稿，
         含逐能力 changeset（v1 评分 vs 市场份额）与证据引用
  jobchangeset-window-diff.json 主案例 2：两窗口 diff 归一为 JobChangeSet
      —— 变化项带证据 JD，供审核命令消费后创建新版本
  jobversions/drafts/*.json     参数化岗位草稿（--job）
      —— 同规则组装：Excel 基线为 v1，该岗位 JD 分布组装 v2 草稿；
         emerging 涌现信号按岗位暂缺，先做两源（基线+JD）
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
DRAFTS = ROOT / "data" / "processed" / "jobversions" / "drafts"

AGENT_TARGET = "AI Agent开发工程师"
# 变化判定用群内排名而非份额换算（份额与 Excel 0-5 评分不同量纲，直接换算不成立）


def _load_common() -> tuple[list[dict], dict, dict[str, dict], list[dict]]:
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
    return positions, caps, parsed, rolemap


def _market_changeset(
    jd_ids: list[str], parsed: dict[str, dict], scores: dict, caps: dict
) -> tuple[Counter, int, list[dict]]:
    """岗位 JD 群的市场技能分布与逐能力 changeset（群内排名规则，岗位通用）。"""
    market: Counter = Counter()
    points: Counter = Counter()
    evid: dict[str, list[str]] = {}
    for jid in jd_ids:
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
        v1 = scores.get(sid)
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
                "evidence_ids": [f"jd:{j}" for j in evid[sid][:5]],
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
                "evidence_ids": None,  # 点级聚合，按需展开
                "note": "基线为能力域级评分，市场证据细化到技能点",
            }
        )
    return market, total, changeset


def _v3_changeset(market, total, caps, prev_req, prev_pref):
    """v3 变更集：新市场 top10 对比已发布 v2 的必备/加分集合。"""
    top10 = [sid for sid, _ in market.most_common(10)]
    cs = []
    for i, sid in enumerate(top10):
        role = "required" if i < 5 else "preferred"
        was = "required" if sid in prev_req else ("preferred" if sid in prev_pref else None)
        if was is None:
            ctype = "add"
        elif was != role:
            ctype = "promote" if role == "required" else "demote"
        else:
            continue
        cs.append(
            {
                "level": "capability",
                "skill_id": sid,
                "name": caps.get(sid, sid),
                "change_type": ctype,
                "v2_role": was,
                "v3_role": role,
                "market_share": round(market[sid] / total, 3),
                "market_rank": i + 1,
                "note": f"v2 为{was or '未收录'}，v3 市场 rank {i + 1}",
            }
        )
    for sid in sorted(prev_req | prev_pref - set(top10)):
        cs.append(
            {
                "level": "capability",
                "skill_id": sid,
                "name": caps.get(sid, sid),
                "change_type": "demote",
                "v2_role": "required" if sid in prev_req else "preferred",
                "v3_role": None,
                "market_share": round(market.get(sid, 0) / total, 3),
                "note": "跌出市场 top10",
            }
        )
    return cs


def _run_position(position_id: str, slug: str, version: int = 2) -> dict:
    """参数化岗位草稿：v2 = Excel 基线 + JD 市场两源；v3 = 已发布 v2 + 扩采后市场重组装。"""
    run = RunContext("jobver", {"cmd": "run", "job": position_id, "version": version})
    positions, caps, parsed, rolemap = _load_common()
    pos = next((p for p in positions if p["position_id"] == position_id), None)
    if pos is None:
        raise SystemExit(f"岗位不存在：{position_id}（见 capability-matrix/positions.jsonl）")
    jd_ids = [rm["jd_id"] for rm in rolemap if rm.get("position_id") == position_id]
    market, total, changeset = _market_changeset(jd_ids, parsed, pos["scores"], caps)
    basis = {
        "v1": f"Excel 专家基线（{position_id} {pos['name']}）",
        "v2": f"市场证据组装（{len(jd_ids)} 条 JD 技能分布）",
    }
    changeset_key = "changeset_vs_v1"
    if version >= 3:
        prev_path = ROOT / "data" / "processed" / "jobversions" / "published" / f"{slug}-v2.json"
        if not prev_path.is_file():
            raise SystemExit(f"v3 需要先发布 {slug}-v2（未找到 {prev_path.name}）")
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
        prev_req = {s["skill_id"] for s in prev.get("required_skill_ids", [])}
        prev_pref = {s["skill_id"] for s in prev.get("preferred_skill_ids", [])}
        changeset = _v3_changeset(market, total, caps, prev_req, prev_pref)
        prev_jd = prev.get("evidence", {}).get("jd_count", "?")
        basis = {
            "v1": basis["v1"],
            "v2": f"已发布 {slug}-v2（{prev_jd} 条 JD，标注方向性待复核）",
            "v3": f"扩采后市场重组装（{len(jd_ids)} 条 JD 技能分布）",
        }
        changeset_key = "changeset_vs_v2"

    draft = {
        "job_id": f"job_{position_id}",
        "version_id": f"{slug}-v{version}-draft-{date.today().strftime('%Y%m%d')}",
        "status": "DRAFT",
        "title": pos["name"],
        "basis": basis,
        "required_skill_ids": [
            {"skill_id": sid, "name": caps.get(sid, sid), "weight": round(n / total, 3)}
            for sid, n in market.most_common(5)
        ],
        "preferred_skill_ids": [
            {"skill_id": sid, "name": caps.get(sid, sid), "weight": round(n / total, 3)}
            for sid, n in market.most_common(10)[5:]
        ],
        "valid_from": date.today().isoformat(),
        "evidence": {
            "evidence_ids": [f"jd:{j}" for j in jd_ids],
            "baseline_evidence_id": f"xlsx:{position_id}",
            "jd_count": len(jd_ids),
        },
        changeset_key: changeset,
        "review_status": "PENDING",
        "generated_by": "jobver v1（确定性组装）",
        "generated_at": date.today().isoformat(),
    }
    DRAFTS.mkdir(parents=True, exist_ok=True)
    out = DRAFTS / f"{draft['version_id']}.json"
    out.write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")

    metrics = {
        "draft_changes": len(changeset),
        "jd_count": len(jd_ids),
        "draft": str(out.relative_to(ROOT)),
    }
    run.finish(metrics)
    return metrics


def cmd_run() -> dict:
    run = RunContext("jobver", {"cmd": "run"})
    positions, caps, parsed, rolemap = _load_common()
    emerging = json.loads(EMERGING.read_text(encoding="utf-8"))

    agent_pos = next(p for p in positions if p["name"] == AGENT_TARGET)
    agent_jd_ids = [
        rm["jd_id"] for rm in rolemap if rm.get("position_id") == agent_pos["position_id"]
    ]

    # 市场侧能力分布（Agent 群）+ 逐能力 changeset（与参数化岗位共用规则）
    market, total, changeset = _market_changeset(agent_jd_ids, parsed, agent_pos["scores"], caps)

    draft = {
        "job_id": f"job_{agent_pos['position_id']}_agent",
        "version_id": f"ai-agent-v2-draft-{date.today().strftime('%Y%m%d')}",
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
            "evidence_ids": [f"jd:{j}" for j in agent_jd_ids],
            "baseline_evidence_id": f"xlsx:{agent_pos['position_id']}",
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
            "evidence_ids": [f"jd:{x['jd_id']}" for x in c["evidence_jds"]],
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
    p_run = sub.add_parser("run")
    p_run.add_argument("--job", default=None, help="position_id（如 pos_01）；缺省跑主案例")
    p_run.add_argument("--slug", default=None, help="版本前缀（如 llm-algo），--job 时必填")
    p_run.add_argument(
        "--version",
        type=int,
        default=2,
        help="版本号：2=对比 Excel 基线；3=对比已发布 v2（扩采复核）",
    )
    args = parser.parse_args(argv)
    if args.job and not args.slug:
        parser.error("--job 需要 --slug（版本前缀，如 llm-algo）")
    result = _run_position(args.job, args.slug, args.version) if args.job else cmd_run()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
