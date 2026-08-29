"""policyget: 政策数据采集（国务院政策文件库统一检索 API，纯 HTTP）。

用法：
    uv run scripts/policyget.py run

数据源：sousuo.www.gov.cn/search-gov/data（公开 JSON，标题/发布时间/发文机关/全文链接）
  - t=zhengcelibrary_gw 国务院文件（核心宏观政策锚点）
  - t=zhengcelibrary_bm 部委文件（就业/职业政策）
新职业目录为静态小数据，人工整理在 data/raw/policy/new-occupations.yml（优于爬取）。
产物：data/processed/policy/policies.jsonl（政策清单 + 全文链接）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "policy" / "policies.jsonl"
API = "https://sousuo.www.gov.cn/search-gov/data"

# 与 30 能力域 / 46 岗位相关的政策关键词
KEYWORDS = [
    "人工智能",
    "数字经济",
    "数据要素",
    "职业技能",
    "数据安全",
    "个人信息保护",
    "平台经济",
    "算力",
    "制造业数字化",
]
LIBRARIES = {"gw": "国务院文件", "bm": "部委文件"}
SLEEP = 1.5


def search(q: str, lib: str, n: int = 20) -> list[dict]:
    url = (
        f"{API}?t=zhengcelibrary_{lib}&q={urllib.parse.quote(q)}"
        f"&timetype=timeqb&sort=pubtime&sortType=1&searchfield=title&p=1&n={n}"
    )
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) Chrome/126",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        vo = json.loads(r.read()).get("searchVO") or {}
    return vo.get("listVO") or []


def _clean(html: str) -> str:
    return re.sub(r"</?em>", "", html or "")


def cmd_run() -> dict:
    run = RunContext("policyget", {"cmd": "run", "keywords": KEYWORDS})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    seen_urls: set[str] = set()
    if OUT.is_file():
        for line in OUT.open(encoding="utf-8"):
            try:
                seen_urls.add(json.loads(line)["url"])
            except Exception:  # noqa: BLE001
                continue
    fresh = 0
    with OUT.open("a", encoding="utf-8") as fh:
        for kw in KEYWORDS:
            for lib, lib_name in LIBRARIES.items():
                try:
                    items = search(kw, lib)
                except Exception as exc:  # noqa: BLE001 - 单库失败不阻塞
                    run.log("policyget", f"{kw}:{lib}", "WARN", detail=str(exc)[:100])
                    time.sleep(SLEEP)
                    continue
                got = 0
                for it in items:
                    url = it.get("url", "") or it.get("purl", "")
                    if not url or url in seen_urls:
                        continue
                    seen_urls.add(url)
                    fh.write(
                        json.dumps(
                            {
                                "policy_id": f"policy:{url.rstrip('/').rsplit('/', 1)[-1][:40]}",
                                "title": _clean(it.get("title")),
                                "puborg": _clean(it.get("puborgStr") or it.get("puborg")),
                                "pubdate": (it.get("pubtimeStr") or "")[:10],
                                "url": url,
                                "keyword": kw,
                                "library": lib_name,
                                "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    got += 1
                fresh += got
                run.log("policyget", f"{kw}:{lib}", "succeeded", count={"new": got})
                time.sleep(SLEEP)
    metrics = {"new": fresh, "total": len(seen_urls)}
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="policyget")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    parser.parse_args(argv)
    print(json.dumps(cmd_run(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
