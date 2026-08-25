"""jdauto: 在远程真实浏览器（CDP）内自动抓取 51job 搜索结果。

原理（实测验证）：冷浏览器的 CDP 导航会被 WAF 软封锁（空结果）；
由真人手动操作"焐热"登录态与 WAF 信誉后，同一浏览器内 goto 正常返回。
因此依赖 jdserve 的远程浏览器（用户已登录、已手动搜索过至少一次）。

前提：远程 Chrome（CDP 9222）在线、已登录、已被手动使用过。
用法：
    uv run scripts/jdauto.py run --keywords "AI Agent 工程师" "AI 应用工程师" [--pages 5]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import sys
import time
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "jd" / "opencli" / "jd_har_raw.jsonl"
DETAIL_OUT = ROOT / "data" / "raw" / "jd" / "opencli" / "jd_har_detail_raw.jsonl"
CDP = "http://127.0.0.1:9222"


def _sleep() -> None:
    time.sleep(random.uniform(2.0, 4.0))


def _keyword_of(url: str) -> str:
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    return (q.get("keyword") or ["?"])[0]


async def cmd_run(keywords: list[str], pages: int) -> dict:
    from playwright.async_api import async_playwright

    run = RunContext("jdauto", {"cmd": "run", "keywords": keywords, "pages": pages})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    known: set[str] = set()
    if OUT.is_file():
        for line in OUT.open(encoding="utf-8"):
            known.add(str(json.loads(line).get("jobId")))

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CDP)
    page = await browser.contexts[0].new_page()

    fh = OUT.open("a", encoding="utf-8")
    total_new = 0
    per_keyword: dict[str, int] = {}
    try:
        for kw in keywords:
            kw_new = 0
            for pageno in range(1, pages + 1):
                captured: list = []

                def on_response(resp) -> None:
                    if "search-pc" in resp.url:
                        captured.append(resp)

                page.on("response", on_response)
                url = (
                    "https://we.51job.com/pc/search"
                    f"?keyword={urllib.parse.quote(kw)}&searchType=post&pageno={pageno}"
                )
                await page.goto(url, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(3500)  # 等签名重试（networkidle 后才发出）
                page.remove_listener("response", on_response)

                items: list[dict] = []
                seen_jid: set[str] = set()
                for resp in captured:
                    if "json" not in resp.headers.get("content-type", ""):
                        continue
                    try:
                        body = await resp.json()
                    except Exception:  # noqa: BLE001 - WAF 挑战页跳过
                        continue
                    for item in (((body or {}).get("resultbody") or {}).get("job") or {}).get(
                        "items"
                    ) or []:
                        jid = str(item.get("jobId") or "")
                        if jid and jid not in seen_jid:
                            seen_jid.add(jid)
                            items.append(item)
                if not items:
                    run.log("jdauto", f"{kw}#{pageno}", "WARN", item_id=kw, count=0)
                    break
                fresh = 0
                for item in items:
                    jid = str(item.get("jobId") or "")
                    if not jid or jid in known:
                        continue
                    known.add(jid)
                    fh.write(
                        json.dumps(
                            {"source_platform": "51job", "keyword": kw, **item}, ensure_ascii=False
                        )
                        + "\n"
                    )
                    fresh += 1
                fh.flush()
                kw_new += fresh
                run.log(
                    "jdauto",
                    f"{kw}#{pageno}",
                    "progress",
                    item_id=kw,
                    count={"page_items": len(items), "fresh": fresh},
                )
                _sleep()
            per_keyword[kw] = kw_new
            total_new += kw_new
    finally:
        fh.close()
        await page.close()
        await pw.stop()
    metrics = {"new": total_new, "per_keyword": per_keyword, "total_file": len(known)}
    run.log("jdauto", "finished", "succeeded", count=metrics)
    run.finish(metrics)
    return metrics


async def cmd_detail(limit: int) -> dict:
    """抓取已收集职位的详情正文（div.job-detail），断点续跑。"""
    from playwright.async_api import async_playwright

    run = RunContext("jdauto", {"cmd": "detail", "limit": limit})
    rows = [json.loads(x) for x in OUT.open(encoding="utf-8")]
    done: set[str] = set()
    if DETAIL_OUT.is_file():
        for line in DETAIL_OUT.open(encoding="utf-8"):
            rec = json.loads(line)
            if rec.get("status") == "ok":
                done.add(rec.get("detail_key"))
    todo = [r for r in rows if str(r.get("jobId")) not in done and r.get("jobHref")][:limit]
    if not todo:
        run.finish({"fetched": 0, "reason": "no_todo"})
        return {"fetched": 0}

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CDP)
    page = await browser.contexts[0].new_page()
    fh = DETAIL_OUT.open("a", encoding="utf-8")
    fetched = usable = 0
    try:
        for row in todo:
            href = row["jobHref"]
            url = href if href.startswith("http") else f"https://we.51job.com{href}"
            rec = {
                "jd_id": f"51job:{row['jobId']}",
                "source_platform": "51job",
                "detail_key": str(row["jobId"]),
            }
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(2500)
                desc = (await page.locator("div.job-detail").first.inner_text()).strip()
                # 标题以搜索层为准（详情页 h1 常被"APP下载"横幅占据）
                rec["status"] = "ok"
                rec["detail"] = {
                    "jobId": str(row["jobId"]),
                    "title": row.get("jobName") or "",
                    "description": desc,
                    "salary": row.get("provideSalaryString") or "",
                    "location": row.get("jobAreaString") or "",
                    "workYear": row.get("workYearString") or "",
                    "degree": row.get("degreeString") or "",
                    "companyType": row.get("fullCompanyName") or row.get("companyName") or "",
                    "companySize": row.get("companySizeString") or "",
                    "companyIndustry": row.get("coIndustryText") or "",
                    "issueDate": row.get("issueDateString") or "",
                    "url": url,
                }
                fetched += 1
                if len(desc) >= 200:
                    usable += 1
            except Exception as exc:  # noqa: BLE001 - 单条失败不中断批次
                rec["status"] = f"error:{type(exc).__name__}"
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fh.flush()
            run.log("detail", str(row["jobId"]), rec["status"][:16], item_id=str(row["jobId"]))
            _sleep()
    finally:
        fh.close()
        await page.close()
        await pw.stop()
    metrics = {"fetched": fetched, "usable": usable, "requested": len(todo)}
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jdauto")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--keywords", nargs="+", required=True)
    p_run.add_argument("--pages", type=int, default=5)
    p_detail = sub.add_parser("detail")
    p_detail.add_argument("--limit", type=int, default=1000)
    args = parser.parse_args(argv)
    if args.cmd == "detail":
        metrics = asyncio.run(cmd_detail(args.limit))
    else:
        metrics = asyncio.run(cmd_run(args.keywords, args.pages))
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
