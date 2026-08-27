"""extract: D6 日报事件抽取 CLI。

用法：
    uv run scripts/extract.py events [--limit N] [--force]

Provider 由 .env 决定：HIRO2_LLM_PROVIDER=mock 离线跑通；默认 anthropic 网关。
幂等：data/processed/wechat-mp/events.jsonl 已存在的 item_id 跳过，--force 重抽。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

from backend.infra.llm.promptspec import load_prompt  # noqa: E402
from backend.infra.llm.provider import build_provider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402
from backend.temporal.service import Article, extract_events  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed" / "wechat-mp"
MAX_BODY_CHARS = 20000
MIN_FEED_CHARS = 150  # 剥标签后低于此长度的 RSS 条目视为纯标题，跳过


def load_articles(limit: int | None, force: bool) -> tuple[list[Article], set[str]]:
    """从 staged 产物装载待抽正文；返回 (文章列表, 已完成 item_id)。"""
    staged = []
    for name in ("reports.jsonl", "reports-unindexed.jsonl"):
        path = PROCESSED / name
        if path.is_file():
            staged += [json.loads(x) for x in path.open(encoding="utf-8")]
    usable = [r for r in staged if r.get("status") in ("ok", "ok_unindexed") and r.get("path")]

    done: set[str] = set()
    events_file = PROCESSED / "events.jsonl"
    if events_file.is_file() and not force:
        done = {json.loads(x)["item_id"] for x in events_file.open(encoding="utf-8")}

    articles = []
    for r in sorted(usable, key=lambda x: x.get("published_at") or x.get("published_date") or ""):
        if r["item_id"] in done:
            continue
        body_path = Path(r["path"])
        if not body_path.is_file():
            body_path = ROOT / r["path"]
        if not body_path.is_file():
            continue
        text = body_path.read_text(encoding="utf-8")[:MAX_BODY_CHARS]
        if not text.strip():
            continue
        articles.append(
            Article(
                item_id=r["item_id"],
                title=r["title"],
                published_at=r.get("published_at") or r.get("published_date"),
                text=text,
            )
        )
        if limit and len(articles) >= limit:
            break
    return articles, done


async def run_extraction(limit: int | None, force: bool) -> dict:
    settings = LLMSettings()
    run = RunContext(
        "extract", {"cmd": "events", "limit": limit, "provider": settings.hiro2_llm_provider}
    )
    spec = load_prompt("report-event")
    provider = build_provider(settings)

    articles, skipped = load_articles(limit, force)
    run.log(
        "extract",
        "articles_loaded",
        "progress",
        count=len(articles),
        detail=f"跳过已完成 {len(skipped)}",
    )

    # 逐篇落盘：长批次中断不丢已完成结果
    PROCESSED.mkdir(parents=True, exist_ok=True)
    events_fh = (PROCESSED / "events.jsonl").open("a", encoding="utf-8")
    issues_fh = (PROCESSED / "events-issues.jsonl").open("a", encoding="utf-8")

    def on_article(_article, events, error) -> None:
        for event in events:
            events_fh.write(event.model_dump_json() + "\n")
        if error is not None:
            issues_fh.write(
                json.dumps(
                    {
                        "item_id": _article.item_id,
                        "error_type": error[0],
                        "error_message": error[1],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        events_fh.flush()
        issues_fh.flush()

    try:
        result = await extract_events(articles, spec, provider, run, on_article=on_article)
    finally:
        events_fh.close()
        issues_fh.close()

    metrics = {
        "articles": len(articles),
        "events": len(result.events),
        "quarantined": len(result.quarantined),
        "prompt_version": spec.version,
        "model_version": provider.model_version,
        "skipped_done": len(skipped),
        **provider.usage.as_dict(),
    }
    run.log("extract", "finished", "succeeded", count=metrics)
    run.finish(metrics)
    return metrics


def load_feed_items(
    limit: int | None, force: bool, days: int | None
) -> tuple[list[Article], set[str]]:
    """装载 RSS FeedItem 为待抽文章；幂等键 feeds:<source_id>:<content_hash 前 12>。

    days：只抽最近 N 天发布的条目（日常增量）；None = 全量（存量回填）。
    """
    from datetime import UTC, datetime, timedelta

    from backend.temporal.feed import RAW_FEEDS, html_to_text

    done: set[str] = set()
    events_file = PROCESSED / "events.jsonl"
    if events_file.is_file() and not force:
        done = {json.loads(x)["item_id"] for x in events_file.open(encoding="utf-8")}
    cutoff = (
        (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds") if days else ""
    )

    items = []
    for path in sorted(RAW_FEEDS.glob("*.jsonl")):
        for line in path.open(encoding="utf-8"):
            try:
                it = json.loads(line)
            except json.JSONDecodeError:
                continue
            pub = it.get("published_at") or ""
            if cutoff and pub and pub < cutoff:
                continue
            item_id = f"feeds:{it['source_id']}:{it['content_hash'][:12]}"
            if item_id in done:
                continue
            text = html_to_text(it.get("content", ""))
            if len(text) < MIN_FEED_CHARS:  # 纯标题/极短条目无事件价值
                continue
            items.append(
                Article(
                    item_id=item_id,
                    title=it.get("title", ""),
                    published_at=pub or None,
                    text=text,
                )
            )
    items.sort(key=lambda a: a.published_at or "")
    if limit:
        items = items[:limit]
    return items, done


async def run_feed_extraction(limit: int | None, force: bool, days: int | None = None) -> dict:
    """RSS 条目 -> report-event prompt -> 同一 events.jsonl 池（下游统一消费）。"""
    settings = LLMSettings()
    run = RunContext(
        "extract",
        {"cmd": "feeds", "limit": limit, "days": days, "provider": settings.hiro2_llm_provider},
    )
    spec = load_prompt("report-event")
    provider = build_provider(settings)

    articles, done = load_feed_items(limit, force, days)
    run.log(
        "extract",
        "feed_items_loaded",
        "progress",
        count=len(articles),
        detail=f"已完成 {len(done)}",
    )

    PROCESSED.mkdir(parents=True, exist_ok=True)
    events_fh = (PROCESSED / "events.jsonl").open("a", encoding="utf-8")
    issues_fh = (PROCESSED / "events-issues.jsonl").open("a", encoding="utf-8")

    def on_article(_article, events, error) -> None:
        for event in events:
            events_fh.write(event.model_dump_json() + "\n")
        if error is not None:
            issues_fh.write(
                json.dumps(
                    {
                        "item_id": _article.item_id,
                        "error_type": error[0],
                        "error_message": error[1],
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
        events_fh.flush()
        issues_fh.flush()

    try:
        result = await extract_events(articles, spec, provider, run, on_article=on_article)
    finally:
        events_fh.close()
        issues_fh.close()

    metrics = {
        "articles": len(articles),
        "events": len(result.events),
        "quarantined": len(result.quarantined),
        "prompt_version": spec.version,
        "model_version": provider.model_version,
        "skipped_done": len(done),
        **provider.usage.as_dict(),
    }
    run.log("extract", "finished", "succeeded", count=metrics)
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="extract")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_events = sub.add_parser("events")
    p_events.add_argument("--limit", type=int, default=None)
    p_events.add_argument("--force", action="store_true")
    p_feeds = sub.add_parser("feeds")
    p_feeds.add_argument("--limit", type=int, default=None)
    p_feeds.add_argument(
        "--days", type=int, default=None, help="只抽最近 N 天条目（日常增量）；缺省全量（存量回填）"
    )
    p_feeds.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    if args.cmd == "events":
        metrics = asyncio.run(run_extraction(args.limit, args.force))
    else:
        metrics = asyncio.run(run_feed_extraction(args.limit, args.force, args.days))
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
