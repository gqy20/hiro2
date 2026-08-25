"""newjob: 主案例 1 —— "AI Agent 工程师"新岗位发现的证据论证。

用法：
    uv run scripts/newjob.py run

五路证据（全部确定性计算，无 LLM）：
  1 标题涌现    Agent 相关 JD 的月度计数与标题变体分化
  2 技能组合    Agent 岗位群的能力域画像 vs 相邻岗位群的余弦距离（"为什么不是既有岗位"）
  3 跨公司扩散  招聘企业的数量与行业分布
  4 信号先行    日报 AI Agent 能力信号时间线与 JD 落地的时间关系
  5 定义卡      从 56 条 JD 聚合五要素（职责/必备/加分/行业）草稿
输出 data/processed/jd-opencli/emerging-agent.json。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
ROLEMAP = ROOT / "data" / "processed" / "jd-opencli" / "jd-role-map.jsonl"
POSITIONS = ROOT / "data" / "processed" / "capability-matrix" / "positions.jsonl"
EVENTS = ROOT / "data" / "processed" / "wechat-mp" / "events.jsonl"
OUT = ROOT / "data" / "processed" / "jd-opencli" / "emerging-agent.json"

AGENT_TARGET = "AI Agent开发工程师"
MIN_CLUSTER = 10  # 参与技能对比的岗位群最小 JD 数
NEIGHBOR_TOP = 4  # 输出最近邻岗位数


def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _dedupe_phrases(phrases: Counter, cap: int) -> list[dict]:
    """按前 6 字去重的短语频次表。"""
    seen: set[str] = set()
    out = []
    for phrase, n in phrases.most_common(60):
        head = phrase[:6]
        if head in seen:
            continue
        seen.add(head)
        out.append({"phrase": phrase, "count": n})
        if len(out) >= cap:
            break
    return out


def cmd_run() -> dict:
    run = RunContext("newjob", {"cmd": "run"})
    parsed = {r["jd_id"]: r for r in (json.loads(x) for x in PARSED.open(encoding="utf-8"))}
    rolemap = [json.loads(x) for x in ROLEMAP.open(encoding="utf-8")]
    positions = {
        p["position_id"]: p["name"]
        for p in (json.loads(x) for x in POSITIONS.open(encoding="utf-8"))
    }
    agent_pid = next((pid for pid, name in positions.items() if name == AGENT_TARGET), None)
    if not agent_pid:
        raise SystemExit(f"标准岗位未找到: {AGENT_TARGET}")

    # 按标准岗位聚簇（仅 AI 域已映射）
    clusters: dict[str, list[dict]] = {}
    for rm in rolemap:
        if rm.get("position_id") and rm["jd_id"] in parsed:
            clusters.setdefault(rm["position_id"], []).append(parsed[rm["jd_id"]])
    agent_jds = clusters.get(agent_pid, [])

    # ---- 证据 1：标题涌现（月度计数 + 标题变体）----
    monthly = Counter()
    for r in agent_jds:
        if r.get("publish_date"):
            monthly[r["publish_date"][:7]] += 1
    title_variants = Counter(r["title"] for r in agent_jds)

    # ---- 证据 2：技能组合距离 ----
    profiles: dict[str, dict[str, float]] = {}
    for pid, rows_ in clusters.items():
        if len(rows_) < MIN_CLUSTER:
            continue
        c: Counter = Counter()
        for r in rows_:
            for x in r.get("resolved") or []:
                c[x["skill_id"]] += 1
        total = sum(c.values()) or 1
        profiles[pid] = {k: v / total for k, v in c.items()}
    agent_profile = profiles.get(agent_pid, {})
    neighbors = sorted(
        (
            (round(_cosine(agent_profile, p), 3), positions.get(pid, pid), pid)
            for pid, p in profiles.items()
            if pid != agent_pid
        ),
        reverse=True,
    )[:NEIGHBOR_TOP]
    # Agent 群内 top 能力域（构成差异的展示）
    caps_names = {
        c["capability_id"]: c["name"]
        for c in json.loads(
            (ROOT / "data/processed/capability-matrix/capabilities.json").read_text(
                encoding="utf-8"
            )
        )["capabilities"]
    }
    agent_top = [
        {"name": caps_names.get(k, k), "share": round(v, 3)}
        for k, v in sorted(agent_profile.items(), key=lambda kv: -kv[1])[:8]
    ]

    # ---- 证据 3：跨公司扩散 ----
    boss_meta = {}
    boss_raw = ROOT / "data/raw/jd/boss/boss_raw.jsonl"
    if boss_raw.is_file():
        for line in boss_raw.open(encoding="utf-8"):
            b = json.loads(line)
            boss_meta[b["encryptJobId"]] = b
    companies: Counter = Counter()
    industries: Counter = Counter()
    for r in agent_jds:
        jid = r["jd_id"].split(":", 1)[-1]
        meta = boss_meta.get(jid)
        if meta:
            companies[meta.get("brandName") or "?"] += 1
            industries[meta.get("brandIndustry") or meta.get("industry") or "?"] += 1

    # ---- 证据 4：信号先行（日报 cap_04 月度加权）----
    from backend.skills.resolver import load_resolver
    from backend.temporal.features import FACT_WEIGHTS

    resolver = load_resolver()
    # Agent 岗位对应能力域：从画像取最大分量对应的能力域（AI Agent 域）
    signal_cap = max(agent_profile, key=agent_profile.get) if agent_profile else "cap_04"
    signal_monthly: Counter = Counter()
    for line in EVENTS.open(encoding="utf-8"):
        e = json.loads(line)
        if not e.get("is_primary", True):
            continue
        day = (e.get("published_at") or "")[:10]
        if not day:
            continue
        w = FACT_WEIGHTS.get(e.get("fact_grade", "report"), 0.6)
        for m in e.get("skill_mentions") or []:
            if resolver.resolve(m).skill_id == signal_cap:
                signal_monthly[day[:7]] += w

    # ---- 证据 5：定义卡五要素（聚合草稿）----
    resp_c: Counter = Counter()
    req_must: Counter = Counter()
    req_plus: Counter = Counter()
    for r in agent_jds:
        for x in r.get("responsibilities") or []:
            resp_c[x] += 1
        for x in r.get("requirements") or []:
            if x.startswith("[必备]"):
                req_must[x.replace("[必备]", "").strip()] += 1
            elif x.startswith("[加分]"):
                req_plus[x.replace("[加分]", "").strip()] += 1
    definition_card = {
        "name": "AI Agent 工程师",
        "core_responsibilities": _dedupe_phrases(resp_c, 6),
        "required_skills": _dedupe_phrases(req_must, 8),
        "preferred_skills": _dedupe_phrases(req_plus, 6),
        "typical_industries": [{"name": k, "count": n} for k, n in industries.most_common(5)],
        "evidence": {
            "jd_count": len(agent_jds),
            "monthly_jd_counts": dict(sorted(monthly.items())),
            "title_variants_top": [
                {"title": t, "count": n} for t, n in title_variants.most_common(10) if n >= 2
            ],
        },
    }

    payload = {
        "target": AGENT_TARGET,
        "evidence": {
            "emergence": {
                "jd_total": len(agent_jds),
                "dated_jds": sum(monthly.values()),
                "monthly": dict(sorted(monthly.items())),
                "title_variants": len(title_variants),
                "title_variants_top": definition_card["evidence"]["title_variants_top"],
            },
            "skill_profile": {
                "agent_top_capabilities": agent_top,
                "neighbors_by_cosine": [
                    {"position": n, "cosine": s, "pid": pid} for s, n, pid in neighbors
                ],
                "min_cluster": MIN_CLUSTER,
            },
            "diffusion": {
                "distinct_companies": len(companies),
                "companies_top": [{"name": k, "count": n} for k, n in companies.most_common(8)],
                "industries_top": [{"name": k, "count": n} for k, n in industries.most_common(8)],
                "note": "公司/行业元数据来自 boss 侧；51job 侧未入此统计",
            },
            "signal_precedence": {
                "capability": caps_names.get(signal_cap, signal_cap),
                "signal_monthly_top": [
                    {"month": m, "weight": round(w, 1)} for m, w in sorted(signal_monthly.items())
                ],
                "signal_total_weight": round(sum(signal_monthly.values()), 1),
                "note": "与 leadtime.json 的 AI Agent 行对照（信号 2025-03 启动，JD 2025-09 落地）",
            },
            "definition_card": definition_card,
        },
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    metrics = {
        "agent_jds": len(agent_jds),
        "monthly_months": len(monthly),
        "title_variants": len(title_variants),
        "neighbors": [n for _, n, _ in neighbors],
        "distinct_companies": len(companies),
        "signal_total_weight": payload["evidence"]["signal_precedence"]["signal_total_weight"],
    }
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="newjob")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    parser.parse_args(argv)
    result = cmd_run()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
