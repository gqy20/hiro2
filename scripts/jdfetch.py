"""jdfetch: 51job 补抓（Playwright 真实浏览器 + 登录态）。

用法：
    准备：从自己浏览器（已登录 51job）F12 -> Network -> 任一请求的 Cookie 头，
          全文粘贴到 data/secrets/51job.cookie.txt（gitignored，不经过对话/代码）。
    uv run scripts/jdfetch.py search --keyword "AI Agent 工程师" --pages 5
    uv run scripts/jdfetch.py detail --limit 40 [--platform 51job]

说明：
- search 捕获 51job 前端 search-pc XHR 的 JSON，字段与既有 raw schema 对齐，增量写入。
- detail 加载职位页并从 DOM 抽取正文，desc>=200 字才计 usable，逐条落盘断点续跑。
- 限速：请求间 2~4s 随机；boss 暂不支持（反爬重，账号风险高，后续另行评估）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "jd" / "opencli"
COOKIE_FILE = ROOT / "data" / "secrets" / "51job.cookie.txt"
SEARCH_OUT = RAW_DIR / "jd_51job_raw_new.jsonl"
DETAIL_OUT = RAW_DIR / "jd_51job_detail_new.jsonl"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126 Safari/537.36"
)


def _sleep() -> None:
    time.sleep(random.uniform(2.0, 4.0))


def _load_cookie_header() -> str:
    if not COOKIE_FILE.is_file():
        raise SystemExit(f"缺少登录态：请把 51job 的 Cookie 头全文写入 {COOKIE_FILE}")
    return COOKIE_FILE.read_text(encoding="utf-8").strip()


def _parse_cookie_header(header: str) -> list[dict]:
    cookies = []
    for part in header.split(";"):
        if "=" in part:
            name, _, value = part.strip().partition("=")
            cookies.append({"name": name, "value": value, "domain": ".51job.com", "path": "/"})
    return cookies


async def _make_page():
    from playwright.async_api import async_playwright

    pw = await async_playwright().start()
    browser = await pw.chromium.launch(headless=True)
    context = await browser.new_context(user_agent=UA, locale="zh-CN")
    await context.add_cookies(_parse_cookie_header(_load_cookie_header()))
    page = await context.new_page()
    return pw, browser, page


async def cmd_search(keyword: str, pages: int) -> dict:
    run = RunContext("jdfetch", {"cmd": "search", "keyword": keyword, "pages": pages})
    from playwright.async_api import Response

    pw, browser, page = await _make_page()
    captured: list[dict] = []
    try:
        for pageno in range(1, pages + 1):
            url = (
                "https://we.51job.com/pc/search"
                f"?keyword={keyword}&searchType=post&sortType=pubtime&pageno={pageno}"
            )
            got: list[dict] = []

            def on_response(resp: Response) -> None:
                if "api/job/search-pc" in resp.url:
                    try:
                        body = resp.json()
                        got.extend((body.get("body") or {}).get("job_list") or [])
                    except Exception:  # noqa: BLE001 - 响应非 JSON 时跳过
                        pass

            page.on("response", on_response)
            await page.goto(url, wait_until="networkidle", timeout=60000)
            page.remove_listener("response", on_response)
            if not got:
                run.log("search", f"page_{pageno}_empty", "WARN", count=pageno)
                break
            captured.extend(got)
            run.log("search", f"page_{pageno}", "progress", count=len(got))
            _sleep()
    finally:
        await browser.close()
        await pw.stop()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    known = set()
    for name in (RAW_DIR / "jd_opencli_raw.jsonl", SEARCH_OUT):
        if name.is_file():
            for line in name.open(encoding="utf-8"):
                known.add(json.loads(line).get("jobId"))
    fresh = [
        {"source_platform": "51job", "keyword": keyword, **item}
        for item in captured
        if item.get("jobId") and item["jobId"] not in known
    ]
    with SEARCH_OUT.open("a", encoding="utf-8") as fh:
        for r in fresh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    metrics = {"keyword": keyword, "pages": pages, "captured": len(captured), "new": len(fresh)}
    run.log("search", "finished", "succeeded", count=metrics)
    run.finish(metrics)
    return metrics


async def cmd_detail(limit: int) -> dict:
    run = RunContext("jdfetch", {"cmd": "detail", "limit": limit})
    rows = []
    for name in (RAW_DIR / "jd_opencli_raw.jsonl", SEARCH_OUT):
        if name.is_file():
            rows += [json.loads(x) for x in name.open(encoding="utf-8")]
    done = set()
    if DETAIL_OUT.is_file():
        for line in DETAIL_OUT.open(encoding="utf-8"):
            done.add(json.loads(line).get("detail_key"))

    # 优先近期发布（issueDate 新的先抓），desc 充足概率更高
    todo = [
        r
        for r in sorted(rows, key=lambda x: x.get("issueDate") or "", reverse=True)
        if r.get("source_platform") == "51job" and r.get("jobId") and r["jobId"] not in done
    ][:limit]
    if not todo:
        run.finish({"fetched": 0, "reason": "no_todo"})
        return {"fetched": 0}

    pw, browser, page = await _make_page()
    fetched = usable = 0
    try:
        for row in todo:
            url = row.get("url")
            if not url:
                continue
            rec = {
                "jd_id": f"51job:{row['jobId']}",
                "source_platform": "51job",
                "detail_key": row["jobId"],
            }
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                desc_el = await page.query_selector(".job_msg, .job-detail, [class*='job_msg']")
                title_el = await page.query_selector("h1, .job-name, [class*='title']")
                rec["status"] = "ok"
                rec["detail"] = {
                    "jobId": row["jobId"],
                    "title": (await title_el.inner_text()).strip() if title_el else "",
                    "description": (await desc_el.inner_text()).strip() if desc_el else "",
                    "salary": row.get("salary") or "",
                    "location": " ".join(filter(None, [row.get("city"), row.get("workYear")])),
                    "companyType": row.get("companyFull") or row.get("company") or "",
                    "companySize": row.get("companyType") or "",
                    "companyIndustry": " / ".join(
                        filter(None, [row.get("companySize"), row.get("industry")])
                    ),
                    "url": url,
                }
                fetched += 1
                if len(rec["detail"]["description"]) >= 200:
                    usable += 1
            except Exception as exc:  # noqa: BLE001 - 单条失败不中断批次
                rec["status"] = f"error:{type(exc).__name__}"
            with DETAIL_OUT.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            run.log("detail", row["jobId"], rec["status"][:20], item_id=row["jobId"])
            _sleep()
    finally:
        await browser.close()
        await pw.stop()
    metrics = {"fetched": fetched, "usable": usable, "requested": len(todo)}
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jdfetch")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_search = sub.add_parser("search")
    p_search.add_argument("--keyword", required=True)
    p_search.add_argument("--pages", type=int, default=5)
    p_detail = sub.add_parser("detail")
    p_detail.add_argument("--limit", type=int, default=40)
    args = parser.parse_args(argv)

    result = asyncio.run(
        cmd_search(args.keyword, args.pages) if args.cmd == "search" else cmd_detail(args.limit)
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
