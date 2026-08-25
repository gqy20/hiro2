"""jdclean: JD 存量修复、搜索层盘点与补抓计划（D5 Phase 0）。

用法：
    uv run scripts/jdclean.py fix    # 修复 detail 字段错位 + 质量分档 -> norm-jd.jsonl
    uv run scripts/jdclean.py index  # 搜索层去重 + 时间窗覆盖盘点 -> jd-search-index.jsonl
    uv run scripts/jdclean.py plan   # 生成补抓需求清单 -> fetch-plan.md

已知数据问题（修复依据）：
- 51job 详情：title 恒为"APP下载"（网页标题），按 jobId join 搜索层找回；
  company/companyType/companySize/companyIndustry 四列整体错位一格；
  location 混入工作年限与招聘人数；约六成 desc 为空（反爬页）。
- boss 详情：字段干净，但搜索层无 issueDate，不能进时间窗，只做标注素材。
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
JD_DIR = ROOT / "data" / "raw" / "jd" / "opencli"
OUT_DIR = ROOT / "data" / "processed" / "jd-opencli"
MIN_DESC = 200

_SALARY = re.compile(r"(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*(万|K|k)")


def parse_salary(raw: str) -> tuple[float, float] | None:
    """'3-5万' -> (30, 50)；'9-14K' -> (9, 14)；失败返回 None。单位统一为 K。"""
    m = _SALARY.search(raw or "")
    if not m:
        return None
    lo, hi = float(m.group(1)), float(m.group(2))
    if m.group(3) == "万":
        lo, hi = lo * 10, hi * 10
    return round(lo), round(hi)


def _detail_dict(rec: dict) -> dict:
    det = rec.get("detail")
    if isinstance(det, str):
        try:
            det = ast.literal_eval(det)
        except (ValueError, SyntaxError):
            return {}
    return det if isinstance(det, dict) else {}


def fix_51job(det: dict, search: dict | None) -> dict:
    """修复 51job 详情的字段错位；title 以搜索层为准。"""
    loc_lines = [x.strip() for x in (det.get("location") or "").split("\n") if x.strip()]
    comp_ind = [x.strip() for x in (det.get("companyIndustry") or "").split("/") if x.strip()]
    return {
        "title": (search or {}).get("title") or "",
        "company": det.get("companyType") or (search or {}).get("company") or "",
        "company_type": det.get("companySize") or "",
        "company_size": comp_ind[0] if comp_ind else "",
        "industry": comp_ind[1] if len(comp_ind) > 1 else (search or {}).get("industry", ""),
        "city": (loc_lines[0] if loc_lines else "") or (search or {}).get("city", ""),
        "work_year": next((x for x in loc_lines if "年" in x or "经验" in x), "")
        or (search or {}).get("workYear", ""),
    }


def fix_boss(det: dict) -> dict:
    """boss 详情字段本就干净，仅做统一形状。"""
    return {
        "title": det.get("name") or "",
        "company": det.get("company") or "",
        "company_type": det.get("stage") or "",
        "company_size": det.get("scale") or "",
        "industry": det.get("industry") or "",
        "city": det.get("city") or "",
        "work_year": det.get("experience") or "",
    }


def _quality(title: str, desc_len: int) -> str:
    if not title:
        return "missing_title"
    if desc_len < MIN_DESC:
        return "insufficient_desc"
    return "usable"


def load_search_index() -> tuple[dict[str, dict], dict[str, dict]]:
    rows = [json.loads(x) for x in (JD_DIR / "jd_opencli_raw.jsonl").open(encoding="utf-8")]
    by_51, by_boss = {}, {}
    for r in rows:
        if r.get("source_platform") == "boss":
            by_boss.setdefault(r.get("security_id") or r.get("url"), r)
        else:
            by_51.setdefault(r.get("jobId"), r)
    return by_51, by_boss


def cmd_fix() -> dict:
    run = RunContext("jdclean", {"cmd": "fix"})
    by_51, by_boss = load_search_index()
    details = [
        json.loads(x) for x in (JD_DIR / "jd_opencli_detail_raw.jsonl").open(encoding="utf-8")
    ]

    records, tiers = [], Counter()
    for rec in details:
        det = _detail_dict(rec)
        desc = det.get("description") or ""
        plat = rec.get("source_platform", "?")
        if plat == "boss":
            fixed = fix_boss(det)
            search = by_boss.get(rec.get("detail_key"))
            publish_date = None
        else:
            search = by_51.get(rec.get("detail_key"))
            fixed = fix_51job(det, search)
            publish_date = (search or {}).get("issueDate", "")[:10] or None
        salary = parse_salary(det.get("salary") or (search or {}).get("salary") or "")
        tier = _quality(fixed["title"], len(desc))
        tiers[tier] += 1
        records.append(
            {
                "jd_id": rec.get("jd_id"),
                "source_platform": plat,
                "source_url": det.get("url") or (search or {}).get("url") or "",
                "publish_date": publish_date,
                "usable_for_time_window": bool(publish_date) and tier == "usable",
                "quality": tier,
                "salary_min_k": salary[0] if salary else None,
                "salary_max_k": salary[1] if salary else None,
                "degree": det.get("degree") or "",
                **fixed,
                "description": desc,
                "description_len": len(desc),
            }
        )

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "norm-jd.jsonl").open("w", encoding="utf-8") as fh:
        for r in records:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    metrics = {
        "details": len(records),
        "tiers": dict(tiers),
        "usable": tiers["usable"],
        "usable_dated": sum(1 for r in records if r["usable_for_time_window"]),
    }
    run.log("jdclean", "fixed", "succeeded", count=metrics)
    run.finish(metrics)
    return metrics


def cmd_index() -> dict:
    run = RunContext("jdclean", {"cmd": "index"})
    rows = [json.loads(x) for x in (JD_DIR / "jd_opencli_raw.jsonl").open(encoding="utf-8")]

    seen: dict[tuple, dict] = {}
    dupes = 0
    for r in rows:
        key = (r.get("source_platform"), r.get("jobId") or r.get("security_id") or r.get("url"))
        if key in seen:
            dupes += 1
            # 保留带日期的一条
            if not seen[key].get("issueDate") and r.get("issueDate"):
                seen[key] = r
        else:
            seen[key] = r
    deduped = list(seen.values())

    months = Counter((r["issueDate"][:7]) for r in deduped if r.get("issueDate"))
    base = sum(n for m, n in months.items() if "2025-09" <= m <= "2025-12")
    obs = sum(n for m, n in months.items() if "2026-03" <= m <= "2026-07")
    no_date = sum(1 for r in deduped if not r.get("issueDate"))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with (OUT_DIR / "jd-search-index.jsonl").open("w", encoding="utf-8") as fh:
        for r in deduped:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    metrics = {
        "raw_rows": len(rows),
        "deduped": len(deduped),
        "duplicates_removed": dupes,
        "no_publish_date": no_date,
        "base_window_2025_09_12": base,
        "obs_window_2026_03_07": obs,
        "months": dict(sorted(months.items())),
    }
    (OUT_DIR / "jd-index-stats.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    run.log("jdclean", "indexed", "succeeded", count={"deduped": len(deduped)})
    run.finish({k: v for k, v in metrics.items() if k != "months"})
    return metrics


PLAN_KEYWORDS = [
    ("P0", "AI Agent 工程师", "主案例 1：新岗位发现"),
    ("P0", "AI 应用工程师", "主案例 2：两窗口 diff"),
    ("P1", "大模型工程师", "能力链核心域"),
    ("P1", "RAG 工程师", "能力链核心域"),
    ("P2", "算法工程师", "首期四方向"),
    ("P2", "机器学习工程师", "首期四方向"),
]


def cmd_plan() -> dict:
    run = RunContext("jdclean", {"cmd": "plan"})
    by_51, _ = load_search_index()
    have = Counter((r.get("keyword") or "?") for r in by_51.values())

    lines = [
        "# JD 补抓需求清单",
        "",
        "执行环境：装有 opencli 与登录会话的机器（旧 hiro 抓取环境）。",
        "执行方式：`uv run hiro-data jd-sample` 与 detail enrich 两步；量由环境变量",
        "`HIRO_OPENCLI_JD_TARGET / _51JOB_TARGET / _BOSS_TARGET` 控制。",
        "产出增量 JSONL 拷回 `hiro2/data/raw/jd/opencli/`（新文件名，不覆盖既有文件）。",
        "",
        "| 优先级 | 关键词 | 用途 | 现有搜索量 | 目标搜索量 | 目标详情量 |",
        "| --- | --- | --- | ---: | ---: | ---: |",
    ]
    for prio, kw, why in PLAN_KEYWORDS:
        lines.append(f"| {prio} | {kw} | {why} | {have.get(kw, 0)} | 150 | 40 |")
    lines += [
        "",
        "注意：",
        "1. 详情优先 51job（有 issueDate，可进时间窗）；boss 无日期仅做标注素材。",
        "2. 51job 详情约六成 desc 为空（反爬页），目标详情量需按 2.5 倍冗余抓取。",
        "3. 时间窗现实：招聘平台只能抓在招职位，2025 基准窗（现仅 16 条）无法补齐。",
        "   主案例 2 两窗口调整为 基准 2026-03~04（现 160 条）/ 观察 2026-06~07（现 281 条），",
        "   05 月为缓冲；或以 Excel 专家基线为基准、2026-03~07 为观察窗。",
        "4. 关键词沿用旧管道 `collect_opencli_jd.py` 的 KEYWORDS 列表，无需改代码。",
        "",
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "fetch-plan.md").write_text("\n".join(lines), encoding="utf-8")
    metrics = {"keywords": len(PLAN_KEYWORDS), "current_keyword_coverage": dict(have)}
    run.finish({"keywords": len(PLAN_KEYWORDS)})
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jdclean")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("fix", "index", "plan"):
        sub.add_parser(name)
    args = parser.parse_args(argv)
    result = {"fix": cmd_fix, "index": cmd_index, "plan": cmd_plan}[args.cmd]()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
