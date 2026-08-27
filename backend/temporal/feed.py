"""Temporal 域 RSS 直连采集：FeedSource 配置读取 + FeedItem 幂等落盘。

CLI 壳在 scripts/rssget.py；cron 每 3 小时与 daily 编排共用本模块。
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2]
FEEDS_YML = ROOT / "data" / "FEEDS.yml"
RAW_FEEDS = ROOT / "data" / "raw" / "feeds"

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126 Safari/537.36"
)
MAX_CONTENT_CHARS = 20000  # ponytail: 防单条超大正文撑爆 raw（截断时 content_truncated 标记）


class FeedItem(BaseModel):
    """原始 RSS 条目（temporal-system.md 最小数据对象）。"""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=40)
    guid: str = Field(min_length=1)
    title: str = ""
    url: str = ""
    published_at: str = ""  # ISO；无信号时空串
    collected_at: str
    content_hash: str = Field(min_length=16, max_length=16)
    content_truncated: bool = False
    content: str = ""


def load_sources(only: str | None = None) -> list[dict]:
    """读 data/FEEDS.yml 的 FeedSource 清单。"""
    import yaml

    cfg = yaml.safe_load(FEEDS_YML.read_text(encoding="utf-8"))
    srcs = cfg["sources"]
    return [s for s in srcs if not only or s["id"] == only]


def to_iso(st: time.struct_time | None) -> str:
    if st is None:
        return ""
    return datetime.fromtimestamp(time.mktime(st), tz=UTC).isoformat(timespec="seconds")


def clip_content(raw: str) -> tuple[str, bool]:
    """正文截断保护：返回 (content, truncated)。"""
    raw = raw.strip()
    if len(raw) > MAX_CONTENT_CHARS:
        return raw[:MAX_CONTENT_CHARS], True
    return raw, False


def html_to_text(html: str) -> str:
    """RSS 正文 HTML -> 纯文本（剥标签 + 实体解码 + 压缩空行）。

    ponytail: 正则够用（RSS 正文无嵌套复杂结构）；复杂版式交给上游网站自己渲染。
    """
    import html as html_mod
    import re

    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S | re.I)
    text = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h[1-6]>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_mod.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def _pick_content(entry) -> str:
    """content 优先，summary 兜底。"""
    raw = ""
    if getattr(entry, "content", None):
        raw = entry.content[0].get("value", "")
    return raw or getattr(entry, "summary", "") or ""


def _seen_guids(out: Path) -> set[str]:
    seen: set[str] = set()
    if out.exists():
        for line in out.open(encoding="utf-8"):
            try:
                seen.add(json.loads(line)["guid"])
            except (json.JSONDecodeError, KeyError):
                continue
    return seen


def fetch_source(source: dict) -> dict:
    """抓单源：feedparser 解析 -> guid 幂等去重 -> 追加新 FeedItem 到 raw。"""
    import feedparser

    sid = source["id"]
    out = RAW_FEEDS / f"{sid}.jsonl"
    seen = _seen_guids(out)

    t0 = time.monotonic()
    parsed = feedparser.parse(source["url"], request_headers={"User-Agent": UA})
    if parsed.bozo and not parsed.entries:
        raise RuntimeError(f"feedparser: {parsed.bozo_exception}"[:120])

    collected = datetime.now(UTC).isoformat(timespec="seconds")
    new_items = []
    for e in parsed.entries:
        guid = getattr(e, "id", "") or getattr(e, "link", "") or getattr(e, "title", "")
        if not guid or guid in seen:
            continue
        content, truncated = clip_content(_pick_content(e))
        pub = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
        item = FeedItem(
            source_id=sid,
            guid=guid,
            title=getattr(e, "title", "").strip(),
            url=getattr(e, "link", ""),
            published_at=to_iso(pub),
            collected_at=collected,
            content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest()[:16],
            content_truncated=truncated,
            content=content,
        )
        new_items.append(item)
        seen.add(guid)

    if new_items:
        RAW_FEEDS.mkdir(parents=True, exist_ok=True)
        with out.open("a", encoding="utf-8") as fh:
            for it in new_items:
                fh.write(json.dumps(it.model_dump(), ensure_ascii=False) + "\n")
    return {
        "source": sid,
        "alias": source["alias"],
        "new": len(new_items),
        "total_feed": len(parsed.entries),
        "stored": len(seen) if out.exists() else 0,
        "ms": int((time.monotonic() - t0) * 1000),
    }
