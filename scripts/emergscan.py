"""emergscan: 涌现岗位扫描器（通用新岗位发现，替代 newjob.py 的硬编码单案例）。

用法：
    uv run scripts/emergscan.py run

逻辑（确定性，零 LLM）：
    1. 从全部 JD 标题抽取候选关键词（英文词组 n-gram + 全大写缩写 + 中文连续段）
    2. 每个关键词计算涌现信号：
       - 月度计数（时间序列）与近/前 90 天增长比
       - 不同标题变体数（跨公司证据）与平台分布
    3. 过滤已知岗位（关键词命中 46 标准岗位名 → 是变体不是新岗位）
    4. 涌现判据：近 90 天 >= 10 且 增长比 >= 1.5（或前窗为 0 = 从无到有）
       且 标题变体 >= 3 且 平台 >= 2
    5. 标题集合高度重叠（Jaccard > 0.5）的候选合并为一个涌现岗位
输出 data/processed/jd-opencli/emerging-roles.json（候选 + 证据）。

验证样本：FDE（Forward Deployed Engineer）—— 2024-01 仅 1 条，
    2026-08 爆发 134 条，跨字节/火山引擎/Anthropic，不在 46 标准岗位 → 应被捞出。
接入：由 forecast_refresh 定时链周期重跑（持续产出新候选），产物供前端/API 消费。
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
OUT = ROOT / "data" / "processed" / "jd-opencli" / "emerging-roles.json"

# 涌现判据参数（可按需调整；判据本身来自"增长 + 多样 + 非已知"三要素）
MIN_TOTAL = 8  # 关键词最少覆盖 JD 数（低于此是噪声）
MIN_VARIANTS = 3  # 最少不同标题数（排除单一公司重复发布）
MIN_PLATFORMS = 2  # 最少平台数（跨来源证据）
MIN_RECENT = 10  # 近 90 天最少 JD 数（近期有效量）
GROWTH_RATIO = 1.5  # 近 90 天 / 前 90 天增长比阈值
MERGE_JACCARD = 0.3  # 标题集合重叠超过此值合并为同一涌现岗位（子集变体归入主簇）
TOP_K = 10  # 最多输出候选数

# 已知技术领域词（这些是领域，不是"新岗位"信号）
KNOWN_DOMAIN = {
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "ai",
    "data science",
    "data scientist",
    "data engineer",
    "big data",
    "自然语言处理",
    "计算机视觉",
    "机器学习",
    "深度学习",
    "人工智能",
    "大模型",
    "大语言模型",
    "llm",
    "nlp",
    "cv",
    "ml",
    "rl",
    "research scientist",
    "research engineer",
    "research intern",
    "reinforcement learning",
    "data center",
    "研发工程师",
    "软件开发工程师",
    "全栈工程师",
    "sr software",
    "sr. software",
    "us",
    "usa",
    "post training",
    "pre training",
}
# 地名/噪声词（非岗位信号）
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
    "london united",
    "public sector",
    "private sector",
    "gtm",
    "ii",
    "iii",
    "iv",
    "financial services",
    "life sciences",
    "healthcare",
    "fintech",
    "human frontier",
    "digital native",
    "enterprise",
    "mid market",
    "london united kingdom",
    "united kingdom",
    "research scientist",
    "研发工程师",
    "data center",
    "figma weave",
    "fellow human",
    "fellow",
}

# 通用词（无处不在，永远不构成"涌现"；主要为省计算，涌现过滤也会自然排除）
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
    "senior staff",
    # 职能泛词（销售/客服/HR/BD 等）：不构成"涌现技术岗位"信号
    "account",
    "executive",
    "solutions",
    "architect",
    "consultant",
    "recruiter",
    "recruiting",
    "sales",
    "marketing",
    "operations",
    "customer",
    "success",
    "enablement",
    "onboarding",
    "business",
    "development",
    "representative",
    "program",
    "product",
    "project",
}


def _keywords(title: str) -> set[str]:
    """标题 -> 候选关键词集：全大写缩写 + 英文词组 n-gram + 中文连续段。"""
    kws: set[str] = set()
    for m in re.finditer(r"\b[A-Z]{2,6}\b", title):
        kws.add(m.group())  # FDE / MCP / SRE 类缩写
    words = [w.lower() for w in re.findall(r"[A-Za-z]{2,}", title)]
    for n in (2, 3, 4):
        for i in range(len(words) - n + 1):
            chunk = words[i : i + n]
            if len(set(chunk)) < len(chunk):
                continue  # 相邻重复词（ai ai 类）
            gram = " ".join(chunk)
            if not any(w in STOP_EN for w in chunk):
                kws.add(gram)
    for seg in re.findall(r"[\u4e00-\u9fff]{3,10}", title):
        kws.add(seg)  # 中文连续段（"前线部署工程师"等）
    return kws


def _parse_day(s: str | None) -> date | None:
    try:
        return date.fromisoformat((s or "")[:10]) if s else None
    except ValueError:
        return None


def cmd_run() -> dict:
    run = RunContext("emergscan", {"cmd": "run"})
    jds = []
    for line in PARSED.open(encoding="utf-8"):
        j = json.loads(line)
        # 只扫 AI 域 JD（销售/职能岗不构成"涌现岗位"信号，is_ai_role 已有标记）
        if j.get("title") and j.get("publish_date") and j.get("is_ai_role"):
            jds.append(j)
    if not jds:
        run.finish({"error": "no jds"}, status="FAILED")
        return {"error": "no jds"}

    known = [
        p.get("name", "").lower() for p in (json.loads(x) for x in POSITIONS.open(encoding="utf-8"))
    ]
    data_end = max(_parse_day(j["publish_date"]) for j in jds)  # 数据末日作基准日
    recent_start = data_end - timedelta(days=90)
    prior_start = data_end - timedelta(days=180)

    # 关键词 -> JD 集合 / 月度计数
    kw_jds: dict[str, list[dict]] = defaultdict(list)
    for j in jds:
        for kw in _keywords(j["title"]):
            kw_jds[kw].append(j)

    candidates = []
    for kw, rows in kw_jds.items():
        if len(rows) < MIN_TOTAL:
            continue
        if kw.lower() in "".join(known) or any(kw.lower() in k for k in known):
            continue  # 命中已知标准岗位名 -> 是变体不是新岗位
        if kw.lower() in KNOWN_DOMAIN or kw.lower() in GEO_NOISE:
            continue  # 已知技术领域词 / 地名噪声，不构成新岗位信号
        if any(g in kw.lower() for g in GEO_NOISE):
            continue  # 关键词包含地名/噪声片段（如 london united kingdom 含 london）
        monthly = Counter(r["publish_date"][:7] for r in rows)
        recent = sum(1 for r in rows if _parse_day(r["publish_date"]) >= recent_start)
        prior = sum(1 for r in rows if prior_start <= _parse_day(r["publish_date"]) < recent_start)
        ratio = (recent / prior) if prior > 0 else None  # None = 从无到有
        variants = len({r["title"] for r in rows})
        platforms = len({r.get("platform", "?") for r in rows})
        # 涌现判据：近期有效量 + 强增长（或从无到有）+ 多样性
        if recent < MIN_RECENT:
            continue
        if ratio is not None and ratio < GROWTH_RATIO:
            continue
        if variants < MIN_VARIANTS or platforms < MIN_PLATFORMS:
            continue
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
                "_jd_ids": {r["jd_id"] for r in rows},
            }
        )

    # 合并标题集合高度重叠的候选（同一现象的不同表述，如 FDE / Forward Deployed）
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
    parser.add_argument("cmd", choices=["run"], nargs="?", default="run")
    parser.parse_args(argv)
    result = cmd_run()
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
