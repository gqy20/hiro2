"""Temporal 事件抽取服务：早报正文 -> ReportEvent 候选。

LLM 只产出结构化候选；解析失败重试，最终失败进隔离队列，绝不静默接受自由文本。
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field

from pydantic import ValidationError

from ..infra.llm.promptspec import PromptSpec
from ..infra.llm.provider import LLMProvider
from .models import ExtractedEvent, ReportEventList

MAX_TEXT_CHARS = 8000
MAX_RETRIES = 2
CONCURRENCY = 15


@dataclass
class Article:
    item_id: str
    title: str
    published_at: str | None
    text: str


@dataclass
class ExtractionResult:
    events: list[ExtractedEvent] = field(default_factory=list)
    quarantined: list[dict[str, str]] = field(default_factory=list)


def _strip_fences(text: str) -> str:
    """剥掉模型可能输出的 Markdown 代码块围栏。"""
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _parse(raw: str) -> ReportEventList:
    try:
        data = json.loads(_strip_fences(raw))
        if not isinstance(data, dict) or "events" not in data:
            raise ValueError("输出必须是包含 events 键的 JSON 对象")
        return ReportEventList.model_validate(data)
    except (json.JSONDecodeError, ValidationError, ValueError) as exc:
        raise ValueError(str(exc)[:300]) from exc


def _user_message(spec: PromptSpec, article: Article) -> str:
    body = article.text[:MAX_TEXT_CHARS]
    return (
        f"早报条目 ID: {article.item_id}\n"
        f"标题: {article.title}\n"
        f"发布时间: {article.published_at or '未知'}\n\n"
        f"正文（Markdown，可能截断）:\n{body}\n\n"
        f"任务: {spec.task}。只输出符合 schema 的 JSON 对象。"
    )


async def extract_one(
    spec: PromptSpec, provider: LLMProvider, article: Article
) -> tuple[list[ExtractedEvent], tuple[str, str] | None]:
    """抽取单篇；返回 (事件列表, (错误类型, 错误信息))。错误非空表示进入隔离队列。"""
    message = _user_message(spec, article)
    max_tokens = int(spec.limits.get("max_tokens", 4000))
    timeout = float(spec.limits.get("timeout_seconds", 60))
    last_type, last_error = "unknown", "unknown"
    for attempt in range(1 + MAX_RETRIES):
        user = (
            message
            if attempt == 0
            else f"{message}\n\n上一次调用失败：{last_error}\n请重新输出符合 schema 的 JSON 对象。"
        )
        try:
            raw = await provider.complete(
                system=spec.system, user=user, max_tokens=max_tokens, timeout=timeout
            )
            parsed = _parse(raw)
        except ValueError as exc:
            last_type, last_error = "validation_failed", str(exc)[:300]
            continue
        except Exception as exc:  # 网关超时/网络瞬断等，计入重试而不是炸掉整批
            last_type, last_error = "api_error", f"{type(exc).__name__}: {exc}"[:300]
            continue
        return (
            [
                ExtractedEvent(
                    **event.model_dump(),
                    event_id=f"{article.item_id}:e{idx:03d}",
                    item_id=article.item_id,
                    published_at=article.published_at,
                    prompt_version=spec.version,
                    model_version=provider.model_version,
                )
                for idx, event in enumerate(parsed.events, start=1)
            ],
            None,
        )
    return [], (last_type, last_error)


async def extract_events(
    articles: list[Article],
    spec: PromptSpec,
    provider: LLMProvider,
    run=None,
    concurrency: int = CONCURRENCY,
    on_article=None,
) -> ExtractionResult:
    """并发抽取一批早报；run 为可选的运行日志对象（需提供 .log 方法）。

    on_article(article, events, error) 在每篇完成时被调用（可异步），
    用于逐篇落盘，长批次中断不丢已完成结果。
    """
    result = ExtractionResult()
    sem = asyncio.Semaphore(concurrency)

    async def worker(article: Article) -> None:
        async with sem:
            events, error = await extract_one(spec, provider, article)
        if error is None:
            result.events.extend(events)
        else:
            error_type, error_message = error
            result.quarantined.append(
                {
                    "item_id": article.item_id,
                    "error_type": error_type,
                    "error_message": error_message,
                }
            )
            if run is not None:
                run.log(
                    "extract",
                    "article_quarantined",
                    "failed",
                    item_id=article.item_id,
                    error_type=error_type,
                    detail=error_message[:80],
                )
        if on_article is not None:
            maybe = on_article(article, events, error)
            if hasattr(maybe, "__await__"):
                await maybe

    done = 0
    started = time.monotonic()

    async def tracked(article: Article) -> None:
        nonlocal done
        await worker(article)
        done += 1
        # 每 25 篇与收尾各打一条完整进度（done/total/速率/ETA），供直接读日志估时
        if run is not None and (done % 25 == 0 or done == len(articles)):
            rate = done / (time.monotonic() - started) * 60
            eta = (len(articles) - done) / max(rate, 0.01)
            run.log(
                "extract",
                "progress",
                "progress",
                count={
                    "done": done,
                    "total": len(articles),
                    "per_min": round(rate, 1),
                    "eta_min": round(eta),
                },
            )

    await asyncio.gather(*(tracked(a) for a in articles))
    return result
