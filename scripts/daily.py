"""daily: 时间情报每日编排（fetch -> 抽取 -> 归一 -> 去重 -> 证据重建）。

用法：
    uv run scripts/daily.py run [--skip-fetch] [--days 7]

单步失败不阻塞后续步骤（记录后继续）；全量重算型下游分钟级完成。
crontab 建议（temporal-system.md 频率）：
    0 */3 * * *  cd <repo> && uv run scripts/rssget.py fetch   # 每 3 小时抓取
    30 8 * * *   cd <repo> && uv run scripts/daily.py run      # 每日信号提取
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402


def _steps(days: int) -> list[tuple[str, object]]:
    import evdedup
    import evidence
    import extract
    import resolve
    import rssget

    async def fetch() -> dict:
        return await rssget.cmd_fetch(None)

    async def extract_daily() -> dict:
        return await extract.run_extraction(None, False)  # 日报增量（无新文秒过）

    async def extract_feeds() -> dict:
        return await extract.run_feed_extraction(None, False, days)

    def resolve_events() -> dict:
        return resolve.cmd_events(None)

    return [
        ("fetch", fetch),
        ("extract_daily", extract_daily),
        ("extract_feeds", extract_feeds),
        ("resolve", resolve_events),
        ("evdedup", evdedup.cmd_run),
        ("evidence", evidence.cmd_build),
    ]


def cmd_run(skip_fetch: bool, days: int) -> dict:
    run = RunContext("daily", {"cmd": "run", "skip_fetch": skip_fetch, "days": days})
    report: dict = {"steps": {}, "failed": []}
    for name, fn in _steps(days):
        if name == "fetch" and skip_fetch:
            report["steps"][name] = {"status": "skipped"}
            continue
        t0 = time.monotonic()
        try:
            metrics = fn() if not asyncio.iscoroutinefunction(fn) else asyncio.run(fn())
            metrics = {k: v for k, v in metrics.items() if not isinstance(v, (list, dict))}
            elapsed = int((time.monotonic() - t0) * 1000)
            report["steps"][name] = {"status": "ok", "ms": elapsed, **metrics}
            run.log("daily", name, "ok", duration_ms=report["steps"][name]["ms"])
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"[:160]
            report["steps"][name] = {"status": "error", "error": msg}
            report["failed"].append(name)
            run.log("daily", name, "error", error=f"{type(exc).__name__}: {exc}"[:160])
    report["status"] = "ok" if not report["failed"] else f"failed_steps={report['failed']}"
    summary = {k: v for k, v in report.items() if k != "steps"}
    run.finish(summary | {"step_count": len(report["steps"])})
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="daily")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("run")
    p.add_argument("--skip-fetch", action="store_true")
    p.add_argument("--days", type=int, default=7, help="RSS 抽取窗口（默认 7 天）")
    args = parser.parse_args(argv)
    report = cmd_run(args.skip_fetch, args.days)
    print(json.dumps(report, ensure_ascii=False, indent=1))
    return 1 if report["failed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
