"""arxivget: arXiv 论文信号采集（四层时间轴的最上游：论文 -> 包 -> 日报 -> JD）。

用法：
    uv run scripts/arxivget.py run --query "AI agent" --year 2023
    uv run scripts/arxivget.py run --all              # 默认关键词表 x 全年份

arXiv API（export.arxiv.org/api/query，Atom XML，公开无需鉴权）按关键词+
提交年份拉 metadata（标题/摘要/日期/分类）；幂等键 arxiv_id。
产物：data/raw/arxiv/papers.jsonl；resolve 归一后聚合
data/processed/arxiv/monthly-skills.json（月 x 能力域提及，事件研究上游）。
限速：官方要求 ~3s/请求。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

from backend.skills.resolver import load_resolver  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT_RAW = ROOT / "data" / "raw" / "arxiv" / "papers.jsonl"
OUT_AGG = ROOT / "data" / "processed" / "arxiv" / "monthly-skills.json"
API = "http://export.arxiv.org/api/query"
NS = {"a": "http://www.w3.org/2005/Atom"}

# 与能力域对齐的检索词（覆盖 30 域中信号价值最高的新兴域）
DEFAULT_QUERIES = [
    "large language model", "AI agent", "retrieval augmented generation",
    "multimodal", "prompt engineering", "fine-tuning", "text embedding",
    "speech recognition", "image generation", "recommendation system",
    "knowledge graph", "reinforcement learning", "federated learning",
]
PAGE = 100
SLEEP = 3.2  # arXiv 官方礼貌限速


def _fetch(query: str, year: int, start: int) -> ET.Element:
    q = f'search_query=all:"{query}" AND submittedDate:[{year}01010000 TO {year}12312359]'
    url = API + "?" + urllib.parse.urlencode(
        {"search_query": q, "start": start, "max_results": PAGE,
         "sortBy": "submittedDate", "sortOrder": "ascending"})
    req = urllib.request.Request(url, headers={"User-Agent": "hiro2-research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return ET.fromstring(r.read())


def fetch_year(query: str, year: int, max_pages: int, seen: set[str],
               sink) -> int:
    """单词单年分页拉取，返回新入库条数。"""
    fresh = 0
    for page in range(max_pages):
        try:
            root = _fetch(query, year, page * PAGE)
        except Exception:  # noqa: BLE001 - 单页失败跳过该词该年余页
            break
        entries = root.findall("a:entry", NS)
        if not entries:
            break
        for e in entries:
            aid = (e.findtext("a:id", "", NS) or "").strip()
            m = re.search(r"abs/([^v]+)", aid)
            if not m:
                continue
            arxiv_id = m.group(1)
            if arxiv_id in seen:
                continue
            seen.add(arxiv_id)
            rec = {
                "arxiv_id": arxiv_id,
                "title": re.sub(r"\s+", " ", e.findtext("a:title", "", NS)).strip(),
                "summary": re.sub(r"\s+", " ", e.findtext("a:summary", "", NS)).strip()[:800],
                "published": (e.findtext("a:published", "", NS) or "")[:10],
                "categories": [c.get("term") for c in e.findall("a:category", NS)],
                "query": query,
                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            }
            sink(json.dumps(rec, ensure_ascii=False) + "\n")
            fresh += 1
        if len(entries) < PAGE:
            break
        time.sleep(SLEEP)
    return fresh


def aggregate() -> dict:
    """标题+摘要的技能提及 -> 月 x 能力域计数。"""
    resolver = load_resolver()
    monthly: dict[str, Counter] = {}
    n = 0
    for line in OUT_RAW.open(encoding="utf-8"):
        p = json.loads(line)
        day = p.get("published") or ""
        if not day:
            continue
        n += 1
        text = f"{p['title']} {p['summary']}".lower()
        cnt = monthly.setdefault(day[:7], Counter())
        # 关键词命中：避免词典长别名在长摘要上误伤，只匹配提及词本身（小写）
        for m in set(re.findall(r"[a-zA-Z][a-zA-Z\- ]{2,30}", text)):
            hit = resolver.resolve(m.strip())
            if hit.skill_id:
                cnt[hit.skill_id] += 1
    out = {"papers": n,
           "monthly": {m: dict(sorted(c.items(), key=lambda x: -x[1]))
                       for m, c in sorted(monthly.items())}}
    OUT_AGG.parent.mkdir(parents=True, exist_ok=True)
    OUT_AGG.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


def cmd_run(queries: list[str], years: list[int], max_pages: int,
            agg_only: bool) -> dict:
    run = RunContext("arxivget", {"cmd": "run", "queries": queries, "years": years})
    OUT_RAW.parent.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    fh = OUT_RAW.open("a", encoding="utf-8")
    per_query: dict[str, int] = {}
    if not agg_only:
        for q in queries:
            fresh_q = 0
            for y in years:
                got = fetch_year(q, y, max_pages, seen, fh.write)
                fresh_q += got
                run.log("arxivget", f"{q[:20]}:{y}", "succeeded", count={"new": got})
                time.sleep(SLEEP)
            per_query[q] = fresh_q
        fh.close()
    agg = aggregate()
    metrics = {"new": sum(per_query.values()), "per_query": per_query,
               "papers_total": agg["papers"], "months": len(agg["monthly"])}
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="arxivget")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--query", nargs="+", default=None,
                       help="检索词；缺省用内置 13 词表")
    p_run.add_argument("--year", nargs="+", type=int, default=None,
                       help="年份列表；缺省 2015..2026")
    p_run.add_argument("--max-pages", type=int, default=2,
                       help="每词每年最多拉几页（100/页）")
    p_run.add_argument("--agg-only", action="store_true", help="只重跑聚合")
    args = parser.parse_args(argv)
    queries = args.query or DEFAULT_QUERIES
    years = args.year or list(range(2015, 2027))
    result = cmd_run(queries, years, args.max_pages, args.agg_only)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
