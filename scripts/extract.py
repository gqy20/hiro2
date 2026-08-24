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
                published_at=r.get("published_at"),
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="extract")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_events = sub.add_parser("events")
    p_events.add_argument("--limit", type=int, default=None)
    p_events.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    metrics = asyncio.run(run_extraction(args.limit, args.force))
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
