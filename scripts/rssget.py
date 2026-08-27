"""rssget: 抓取 FEEDS.yml 直连 RSS 源（CLI 壳，域逻辑在 backend/temporal/feed.py）。

用法：
    uv run scripts/rssget.py fetch [--only SOURCE_ID]

产物：data/raw/feeds/<source_id>.jsonl（追加式，guid 幂等去重）。
失败源记状态不阻塞其他源；每次运行带 run_id 结构化日志。
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402


async def cmd_fetch(only: str | None) -> dict:
    from backend.temporal.feed import fetch_source, load_sources

    run = RunContext("rssget", {"cmd": "fetch", "only": only})
    sources = load_sources(only)
    results, errors = [], []

    def one(src: dict) -> None:
        try:
            r = fetch_source(src)
            results.append(r)
            run.log("rssget", src["id"], "ok", count=r["new"], duration_ms=r["ms"])
        except Exception as exc:  # noqa: BLE001
            errors.append({"source": src["id"], "error": f"{type(exc).__name__}: {exc}"[:140]})
            run.log("rssget", src["id"], "error", error=f"{type(exc).__name__}: {exc}"[:140])

    def run_all() -> None:
        with concurrent.futures.ThreadPoolExecutor(8) as ex:
            list(ex.map(one, sources))

    await asyncio.to_thread(run_all)
    metrics = {
        "sources": len(sources),
        "ok": len(results),
        "failed": len(errors),
        "new_items": sum(r["new"] for r in results),
        "by_source": sorted(results, key=lambda r: -r["new"]),
        "errors": errors,
    }
    run.finish({k: v for k, v in metrics.items() if not isinstance(v, (list, dict))})
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="rssget")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("fetch")
    p.add_argument("--only")
    args = parser.parse_args(argv)
    result = asyncio.run(cmd_fetch(args.only))
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
