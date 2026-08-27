"""feedtest: 逐个测试直连 RSS 源可用性（HTTP 200 + RSS/Atom 特征 + 条目数）。

用法：
    uv run scripts/feedtest.py [--timeout 15] [--workers 16]

读 rss2cubox feeds.txt 的 [direct] 段（仅 http(s) 开头的真直连），并发 GET
前 64KB 判定，输出按优先级分组的结果表 + data/processed/feeds/feedtest.json。
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
FEEDS_TXT = Path.home() / "workspace" / "project" / "2605" / "rss2cubox" / "feeds.txt"
OUT = ROOT / "data" / "processed" / "feeds" / "feedtest.json"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126 Safari/537.36"
)


def load_direct() -> list[dict]:
    """解析 [direct] 段：优先级<TAB>URL # 别名；只收 http(s) 开头的真直连。"""
    feeds, section = [], None
    for line in FEEDS_TXT.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("["):
            section = s
            continue
        if section != "[direct]":
            continue
        m = re.match(r"^(\d*)\s+(https?://\S+?)(?:\s+#\s*(.+))?$", s)
        if not m:
            continue
        feeds.append(
            {
                "pri": int(m.group(1)) if m.group(1) else 0,
                "url": m.group(2),
                "alias": m.group(3) or m.group(2),
            }
        )
    return feeds


def check(feed: dict, timeout: int) -> dict:
    """GET 前 64KB：状态 + feed 特征 + 条目数 + 耗时。"""
    req = urllib.request.Request(feed["url"], headers={"User-Agent": UA})
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read(65536).decode("utf-8", errors="replace")
            status = resp.status
    except Exception as exc:  # noqa: BLE001
        return {
            **feed,
            "ok": False,
            "reason": f"{type(exc).__name__}: {exc}"[:90],
            "ms": int((time.monotonic() - t0) * 1000),
        }
    ms = int((time.monotonic() - t0) * 1000)
    is_feed = any(tag in body for tag in ("<rss", "<feed", "<rdf:RDF"))
    items = max(len(re.findall(r"<item[ >]", body)), len(re.findall(r"<entry[ >]", body)))
    return {
        **feed,
        "ok": status == 200 and is_feed,
        "status": status,
        "is_feed": is_feed,
        "items": items,
        "ms": ms,
        "reason": ""
        if status == 200 and is_feed
        else (f"http {status}" if status != 200 else "非 RSS/Atom 内容"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="feedtest")
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--workers", type=int, default=16)
    args = parser.parse_args(argv)

    feeds = load_direct()
    print(f"[direct] 真直连 {len(feeds)} 个（timeout={args.timeout}s, workers={args.workers}）…")
    results = []
    with concurrent.futures.ThreadPoolExecutor(args.workers) as ex:
        futs = [ex.submit(check, f, args.timeout) for f in feeds]
        for fut in concurrent.futures.as_completed(futs):
            r = fut.result()
            results.append(r)
            mark = "✓" if r["ok"] else "✗"
            items = r.get("items", "-")
            reason = r.get("reason", "")[:40]
            print(f"  {mark} p{r['pri']} {r['alias'][:28]:28} {items}条 {r['ms']}ms {reason}")

    ok = [r for r in results if r["ok"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "tested": len(results),
                "ok": len(ok),
                "by_pri": {
                    str(p): sum(1 for r in ok if r["pri"] == p)
                    for p in sorted({r["pri"] for r in results}, reverse=True)
                },
                "results": sorted(results, key=lambda r: (-r["pri"], not r["ok"], r["alias"])),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n可用 {len(ok)}/{len(results)}，按优先级：")
    for p in sorted({r["pri"] for r in results}, reverse=True):
        total = sum(1 for r in results if r["pri"] == p)
        good = sum(1 for r in ok if r["pri"] == p)
        print(f"  优先级 {p}: {good}/{total}")
    print(f"报告: {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
