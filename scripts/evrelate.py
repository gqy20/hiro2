"""evrelate: D7 证据关系层——支持/反证标记与统一审核队列。

关系（规则化，零 LLM）：
  supports    JD 证据（resolved 含 skill_id）-> JobVersion 必备/加分技能字段
  contradicts changeset add 项（基线无、市场证据进版本）-> 对专家基线反证
队列（统一 review-queue.jsonl，幂等重建）：
  cross_source_conflict  专家基线含技能但版本市场证据零提及（方向相反，入队裁决）
  single_source_hotspot  技能 JD 提及仅来自单一 platform 且 >=5 次
  low_confidence         版本引用的 JD 证据里 quality < 0.6
  （2026-08-29 实测三者为 0：JD 池多平台化后 28 技能 27 个多源、JD 质量 0.8 恒定、
   changeset 全 add 型——为数据实情，队列保留规则持续生效）
用法：uv run scripts/evrelate.py run
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EV = ROOT / "data/processed/evidence/evidence.jsonl"
PUB = ROOT / "data/processed/jobversions/published"
OUT_REL = ROOT / "data/processed/evidence/relations.jsonl"
OUT_Q = ROOT / "data/processed/evidence/review-queue.jsonl"

SINGLE_SOURCE_MIN = 5  # 单源热点：JD 提及 >=5 次且仅一个 platform
LOW_CONF = 0.6


def cmd_run() -> dict:
    run = RunContext("evrelate", {"cmd": "run"})
    ev = [json.loads(ln) for ln in EV.open(encoding="utf-8")]
    by_id = {e["evidence_id"]: e for e in ev}

    # jd_id -> {skill_id 集合, platform}（关系与单源检测共用）
    jd_skills: dict[str, set[str]] = {}
    jd_platform: dict[str, str] = {}
    for e in ev:
        if e["claim_type"] != "job_requirement":
            continue
        jd_id = e["source_span"]["jd_id"]
        jd_platform[jd_id] = e["source_id"]
    for line in (ROOT / "data/processed/jd-opencli/jd-parsed-asof.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        jd_skills[r["jd_id"]] = {x["skill_id"] for x in (r.get("resolved") or [])}

    # 技能 -> platform 提及计数（单源热点）
    skill_plat: dict[str, Counter] = defaultdict(Counter)
    for jd_id, caps in jd_skills.items():
        p = jd_platform.get(jd_id)
        if p:
            for cap in caps:
                skill_plat[cap][p] += 1

    relations = []
    queue = []

    versions = sorted(PUB.glob("*.json"))
    for vf in versions:
        v = json.loads(vf.read_text(encoding="utf-8"))
        vid = v["version_id"]
        ev_ids = (v.get("evidence") or {}).get("evidence_ids") or []
        jd_ids = [i[3:] for i in ev_ids if i.startswith("jd:")]

        req_caps = {s["skill_id"] for s in v.get("required_skill_ids") or []}
        pref_caps = {s["skill_id"] for s in v.get("preferred_skill_ids") or []}
        field_caps = req_caps | pref_caps

        # supports：版本引用的 JD 证据提及技能 -> 字段
        sup_by_cap: dict[str, list[str]] = defaultdict(list)
        for jd_id in jd_ids:
            for cap in jd_skills.get(jd_id, set()) & field_caps:
                relations.append({
                    "relation_id": f"rel:{vid}:{jd_id}:{cap}",
                    "evidence_id": f"jd:{jd_id}",
                    "target": {"type": "job_version_skill", "version_id": vid,
                               "skill_id": cap,
                               "field": "required" if cap in req_caps else "preferred"},
                    "direction": "supports",
                    "rule": "jd_resolved_mentions_skill",
                })
                sup_by_cap[cap].append(f"jd:{jd_id}")

        # contradicts：changeset add 项 = 市场证据把基线没有的技能推进版本 -> 对基线反证
        base_ev = (v.get("evidence") or {}).get("baseline_evidence_id")
        cs = v.get("changeset_vs_v1") or v.get("changeset_vs_v2") or []
        if base_ev:
            for c in cs:
                if c.get("change_type") == "add":
                    cap_domain = str(c.get("skill_id", "")).split(".")[0]
                    sup = sup_by_cap.get(cap_domain) or []
                    relations.append({
                        "relation_id": f"rel:{vid}:base:{c.get('skill_id')}",
                        "evidence_id": sup[0] if sup else base_ev,
                        "supporting_evidence_ids": sup[:5],
                        "target": {"type": "expert_baseline_skill",
                                   "evidence_id": base_ev,
                                   "skill_id": c.get("skill_id")},
                        "direction": "contradicts",
                        "rule": "market_added_absent_from_baseline",
                        "note": c.get("note"),
                    })

        # 跨源冲突：基线技能 vs 市场证据零提及（弱反证，入队人工裁决）
        base_ev = (v.get("evidence") or {}).get("baseline_evidence_id")
        if base_ev and base_ev in by_id:
            # changeset 为列表：[{level, skill_id, change_type: add|promote|demote|keep, ...}]
            # 基线侧技能 = 非 add 项（v1/v2 已有：keep/demote），能力域级取整域
            cs = v.get("changeset_vs_v1") or v.get("changeset_vs_v2") or []
            base_caps = {c.get("skill_id", "").split(".")[0] for c in cs
                         if c.get("change_type") != "add"}
            mentioned = set()
            for jd_id in jd_ids:
                mentioned |= jd_skills.get(jd_id, set())
            for cap in base_caps - mentioned:
                if cap:
                    queue.append({
                        "queue_id": f"q:conflict:{vid}:{cap}",
                        "kind": "cross_source_conflict",
                        "severity": "medium",
                        "subject": f"{vid} 技能 {cap}：专家基线含、市场证据零提及",
                        "evidence_ids": [base_ev] + [f"jd:{j}" for j in jd_ids[:5]],
                        "detail": {"version_id": vid, "skill_id": cap,
                                   "baseline": base_ev, "market_jd_count": len(jd_ids)},
                    })

        # 低置信：版本引用的 JD 证据 quality < 0.6（jd 固定 0.8，实际捕获兜底）
        low = [i for i in ev_ids if i in by_id and by_id[i].get("quality_score", 1) < LOW_CONF]
        if low:
            queue.append({
                "queue_id": f"q:lowconf:{vid}",
                "kind": "low_confidence",
                "severity": "low",
                "subject": f"{vid} 引用低置信证据 {len(low)} 条",
                "evidence_ids": low[:10],
                "detail": {"version_id": vid, "count": len(low)},
            })

    # 单源热点（全局，技能级）
    for cap, plats in skill_plat.items():
        if len(plats) == 1 and sum(plats.values()) >= SINGLE_SOURCE_MIN:
            only = next(iter(plats))
            queue.append({
                "queue_id": f"q:singlesrc:{cap}",
                "kind": "single_source_hotspot",
                "severity": "low",
                "subject": f"技能 {cap} 的 JD 提及 {sum(plats.values())} 次全部来自 {only}",
                "evidence_ids": [],
                "detail": {"skill_id": cap, "platform": only,
                           "count": sum(plats.values())},
            })

    # 幂等重写
    OUT_REL.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in relations), encoding="utf-8")
    OUT_Q.write_text(
        "".join(json.dumps(q, ensure_ascii=False) + "\n" for q in queue), encoding="utf-8")

    metrics = {
        "versions": len(versions),
        "relations": len(relations),
        "supports": sum(1 for r in relations if r["direction"] == "supports"),
        "queue_total": len(queue),
        "queue_by_kind": dict(Counter(q["kind"] for q in queue)),
    }
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evrelate")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    parser.parse_args(argv)
    print(json.dumps(cmd_run(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
