"""emergscan: 涌现岗位扫描器（通用新岗位发现，替代 newjob.py 的硬编码单案例）。

用法：
    uv run scripts/emergscan.py run

逻辑（确定性，零 LLM）：
    1. 从全部 AI 域 JD 标题抽取候选关键词（英文词组 n-gram + 全大写缩写 + 中文连续段）
    2. 每个关键词计算涌现信号：月度计数、近/前 90 天增长比、标题变体数、平台分布
    3. 内容聚合：候选簇内 JD 的 resolved 技能、职责短语、要求短语、行业场景频次
    4. 过滤已知岗位/技术领域/地名噪声
    5. 涌现判据：近 90 天 >= 10 且 增长比 >= 1.5（或前窗为 0）且 变体 >= 3 且 平台 >= 2
    6. 标题集合高度重叠（Jaccard > 0.3）的候选合并为一个涌现岗位
输出 data/processed/jd-opencli/emerging-roles.json（候选 + 证据 + 内容画像）。

验证样本：FDE（Forward Deployed Engineer）—— 2024-01 仅 1 条，2026-08 爆发 134 条，
    跨字节/火山引擎/Anthropic，不在 46 标准岗位 → 应被捞出且带完整内容画像。
接入：由 forecast_refresh 定时链周期重跑（持续产出新候选），产物经 service.py 消费到前端。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
POSITIONS = ROOT / "data" / "processed" / "capability-matrix" / "positions.jsonl"
CAPS = ROOT / "data" / "processed" / "capability-matrix" / "capabilities.json"
OUT = ROOT / "data" / "processed" / "jd-opencli" / "emerging-roles.json"

# 涌现判据
MIN_TOTAL = 8
MIN_VARIANTS = 3
MIN_PLATFORMS = 2
MIN_RECENT = 10
GROWTH_RATIO = 1.5
MERGE_JACCARD = 0.3
TOP_K = 10

# 通用词（不构成涌现信号）
STOP_EN = {
    "engineer",
    "engineering",
    "senior",
    "staff",
    "junior",
    "manager",
    "lead",
    "specialist",
    "expert",
    "associate",
    "intern",
    "director",
    "head",
    "vp",
    "full",
    "time",
    "part",
    "remote",
    "hybrid",
    "onsite",
}

# 已知技术领域词（不是新岗位）
KNOWN_DOMAIN = {
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "ai",
    "data science",
    "data scientist",
    "data engineer",
    "big data",
    "natural language",
    "computer vision",
    "reinforcement learning",
    "rl",
    "ml",
    "llm",
    "nlp",
    "cv",
    "generative ai",
    "applied ai",
    "machine",
    "deep",
    "artificial",
    "intelligence",
    "自然语言处理",
    "计算机视觉",
    "机器学习",
    "深度学习",
    "人工智能",
    "大模型",
    "大语言模型",
    "研发工程师",
    "软件开发工程师",
    "全栈工程师",
    "data center",
    "research scientist",
    "research engineer",
    "sr software",
    "solutions architect",
    "solution architect",
    "account executive",
    "technical program",
    "product designer",
    "gtm",
    "product marketing",
    "sr product",
    "ai product",
    "product manager",
    "account manager",
    "pre sales",
    "sales engineer",
    "customer success",
}

# 地名/噪声词（含子串匹配）
GEO_NOISE = {
    "united kingdom",
    "london",
    "singapore",
    "tokyo",
    "new york",
    "san francisco",
    "united states",
    "europe",
    "asia",
    "emea",
    "apac",
    "north america",
    "ii",
    "iii",
    "iv",
    "public sector",
    "private sector",
    "financial services",
    "life sciences",
    "healthcare",
    "fintech",
    "human frontier",
    "digital native",
    "enterprise",
    "mid market",
    "figma weave",
    "fellow",
    "sr software",
    "us",
    "usa",
}


def _keywords(title: str) -> set[str]:
    """标题 -> 候选关键词集：全大写缩写 + 英文词组 n-gram + 中文连续段。"""
    kws: set[str] = set()
    for m in re.finditer(r"\b[A-Z]{2,6}\b", title):
        kws.add(m.group())
    words = [w.lower() for w in re.findall(r"[A-Za-z]{2,}", title)]
    for n in (2, 3, 4):
        for i in range(len(words) - n + 1):
            chunk = words[i : i + n]
            if len(set(chunk)) < len(chunk):
                continue
            if any(w in STOP_EN for w in chunk):
                continue
            kws.add(" ".join(chunk))
    for seg in re.findall(r"[\u4e00-\u9fff]{3,10}", title):
        kws.add(seg)
    return kws


def _parse_day(s: str | None) -> date | None:
    try:
        return date.fromisoformat((s or "")[:10]) if s else None
    except ValueError:
        return None


def _dedupe_phrases(phrases: Counter, cap: int = 6) -> list[dict]:
    """按前 6 字去重的短语频次表。"""
    seen: set[str] = set()
    out: list[dict] = []
    for phrase, n in phrases.most_common(60):
        head = phrase[:6]
        if head in seen:
            continue
        seen.add(head)
        out.append({"phrase": phrase, "count": n})
        if len(out) >= cap:
            break
    return out


def _aggregate_content(rows: list[dict], caps_names: dict[str, str]) -> dict:
    """候选簇内 JD 的内容聚合：技能画像 + 职责/要求短语 + 行业场景。"""
    skill_c: Counter = Counter()
    resp_c: Counter = Counter()
    req_c: Counter = Counter()
    scen_c: Counter = Counter()
    for r in rows:
        for x in r.get("resolved") or []:
            skill_c[x["skill_id"]] += 1
        for ph in r.get("responsibilities") or []:
            if isinstance(ph, str) and 4 <= len(ph) <= 60:
                resp_c[ph.strip()] += 1
        for ph in r.get("requirements") or []:
            if isinstance(ph, str) and 4 <= len(ph) <= 60:
                # 剥掉 [必备]/[加分] 前缀标签
                clean = re.sub(r"^\[.*?\]\s*", "", ph.strip())
                if 4 <= len(clean) <= 60:
                    req_c[clean] += 1
        for sc in r.get("scenarios") or []:
            if isinstance(sc, str) and 2 <= len(sc) <= 20:
                scen_c[sc.strip()] += 1
        # 从标题提取行业词（英文 JD 常带行业后缀）
        title = r.get("title", "")
        for w in (
            "制造",
            "金融",
            "医疗",
            "零售",
            "电商",
            "营销",
            "教育",
            "Manufacturing",
            "Marketing",
            "Finance",
            "Healthcare",
            "Retail",
            "Communications",
            "Media",
            "Entertainment",
            "Digital",
            "Games",
        ):
            if w.lower() in title.lower():
                scen_c[w] += 1
    return {
        "top_skills": [
            {"name": caps_names.get(k, k), "count": v} for k, v in skill_c.most_common(8)
        ],
        "core_responsibilities": _dedupe_phrases(resp_c, cap=6),
        "core_requirements": _dedupe_phrases(req_c, cap=8),
        "scenarios": _dedupe_phrases(scen_c, cap=5),
    }


def cmd_run() -> dict:
    run = RunContext("emergscan", {"cmd": "run"})
    jds = []
    for line in PARSED.open(encoding="utf-8"):
        j = json.loads(line)
        if j.get("title") and j.get("publish_date") and j.get("is_ai_role"):
            jds.append(j)
    if not jds:
        run.finish({"error": "no jds"}, status="FAILED")
        return {"error": "no jds"}

    known = [
        p.get("name", "").lower() for p in (json.loads(x) for x in POSITIONS.open(encoding="utf-8"))
    ]
    caps_names = {
        c["capability_id"]: c["name"]
        for c in json.loads(CAPS.read_text(encoding="utf-8"))["capabilities"]
    }
    data_end = max(_parse_day(j["publish_date"]) for j in jds)
    recent_start = data_end - timedelta(days=90)
    prior_start = data_end - timedelta(days=180)

    kw_jds: dict[str, list[dict]] = defaultdict(list)
    for j in jds:
        for kw in _keywords(j["title"]):
            kw_jds[kw].append(j)

    candidates = []
    for kw, rows in kw_jds.items():
        if len(rows) < MIN_TOTAL:
            continue
        if kw.lower() in KNOWN_DOMAIN or kw.lower() in GEO_NOISE:
            continue
        if any(g in kw.lower() for g in GEO_NOISE):
            continue
        if any(kw.lower() in k for k in known):
            continue
        monthly = Counter(r["publish_date"][:7] for r in rows)
        recent = sum(1 for r in rows if _parse_day(r["publish_date"]) >= recent_start)
        prior = sum(1 for r in rows if prior_start <= _parse_day(r["publish_date"]) < recent_start)
        ratio = (recent / prior) if prior > 0 else None
        variants = len({r["title"] for r in rows})
        platforms = len({r.get("platform", "?") for r in rows})
        if recent < MIN_RECENT:
            continue
        if ratio is not None and ratio < GROWTH_RATIO:
            continue
        if variants < MIN_VARIANTS or platforms < MIN_PLATFORMS:
            continue
        content = _aggregate_content(rows, caps_names)
        candidates.append(
            {
                "keyword": kw,
                "total": len(rows),
                "recent_90d": recent,
                "prior_90d": prior,
                "growth_ratio": round(ratio, 2) if ratio else None,
                "monthly": dict(sorted(monthly.items())),
                "title_variants": variants,
                "platforms": platforms,
                "sample_titles": sorted({r["title"] for r in rows})[:5],
                **content,
                "_jd_ids": {r["jd_id"] for r in rows},
            }
        )

    # 合并标题集合高度重叠的候选
    candidates.sort(key=lambda c: -c["total"])
    merged: list[dict] = []
    for c in candidates:
        dup = next(
            (
                m
                for m in merged
                if len(c["_jd_ids"] & m["_jd_ids"]) / max(1, len(c["_jd_ids"] | m["_jd_ids"]))
                > MERGE_JACCARD
            ),
            None,
        )
        if dup:
            if c["total"] > dup["total"]:
                dup.update({k: c[k] for k in c if k != "_jd_ids"})
                dup["_jd_ids"] |= c["_jd_ids"]
                dup["aliases"] = sorted({*dup.get("aliases", []), dup["keyword"], c["keyword"]})
            else:
                dup["aliases"] = sorted({*dup.get("aliases", []), c["keyword"]})
            continue
        merged.append(c)
    for m in merged:
        m.pop("_jd_ids")
    merged = merged[:TOP_K]

    payload = {
        "as_of": str(data_end),
        "criteria": {
            "min_recent_90d": MIN_RECENT,
            "growth_ratio": GROWTH_RATIO,
            "min_title_variants": MIN_VARIANTS,
            "min_platforms": MIN_PLATFORMS,
        },
        "candidates": merged,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    run.finish({"as_of": str(data_end), "candidates": len(merged)})
    return {
        "as_of": str(data_end),
        "candidates": len(merged),
        "top": [c["keyword"] for c in merged[:5]],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="emergscan")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    parser.parse_args(argv)
    result = cmd_run()
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
