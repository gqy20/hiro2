"""jdlisten: 被动监听远程浏览器（CDP）里的 51job 搜索响应并落盘。

前提：jdserve 起的 Chrome（CDP 9222）正被真人通过 noVNC 操作。
用法：
    uv run scripts/jdlisten.py            # 持续运行，Ctrl+C 停止
捕获 search-pc 的 JSON 职位列表，按 jobId 去重增量写入
data/raw/jd/opencli/jd_har_raw.jsonl。
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.parse
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "raw" / "jd" / "opencli" / "jd_har_raw.jsonl"
CDP = "http://127.0.0.1:9222"


def _keyword(url: str) -> str:
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    return (q.get("keyword") or ["?"])[0]


async def main() -> None:
    from playwright.async_api import async_playwright

    OUT.parent.mkdir(parents=True, exist_ok=True)
    known = set()
    if OUT.is_file():
        for line in OUT.open(encoding="utf-8"):
            known.add(json.loads(line).get("jobId"))
    counts: Counter = Counter()
    fh = OUT.open("a", encoding="utf-8")

    pw = await async_playwright().start()
    browser = await pw.chromium.connect_over_cdp(CDP)
    print(f"已连接 CDP，已有 {len(known)} 条；开始监听（Ctrl+C 停止）...", file=sys.stderr)

    def bind(page) -> None:
        async def on_response(resp) -> None:
            nonlocal known
            if "api/job/search-pc" not in resp.url:
                return
            if "json" not in resp.headers.get("content-type", ""):
                return
            try:
                body = await resp.json()
            except Exception:  # noqa: BLE001 - WAF 挑战页等跳过
                return
            items = (((body or {}).get("resultbody") or {}).get("job") or {}).get("items") or []
            fresh = 0
            for item in items:
                jid = str(item.get("jobId") or "")
                if not jid or jid in known:
                    continue
                known.add(jid)
                fh.write(
                    json.dumps(
                        {"source_platform": "51job", "keyword": _keyword(resp.url), **item},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                fresh += 1
            fh.flush()
            if fresh:
                counts[_keyword(resp.url)] += fresh
                total = sum(counts.values())
                print(f"[+] {_keyword(resp.url)}: +{fresh}（累计 {total}）", file=sys.stderr)

        page.on("response", on_response)

    for ctx in browser.contexts:
        for p in ctx.pages:
            bind(p)
    browser.on("page", bind) if hasattr(browser, "on") else None
    # contexts 变化时也绑定（新开窗口）
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        fh.close()
        print(f"结束：本次新增 {sum(counts.values())} 条 -> {OUT}", file=sys.stderr)
        await pw.stop()


if __name__ == "__main__":
    asyncio.run(main())
