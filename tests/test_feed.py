"""temporal/feed 纯逻辑测试：FeedItem 模型、截断、guid 幂等（不联网）。"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.temporal import feed


def test_clip_content_truncates() -> None:
    content, truncated = feed.clip_content("x" * (feed.MAX_CONTENT_CHARS + 5))
    assert truncated is True
    assert len(content) == feed.MAX_CONTENT_CHARS
    content, truncated = feed.clip_content("  短文  ")
    assert (content, truncated) == ("短文", False)


def test_to_iso_handles_none() -> None:
    assert feed.to_iso(None) == ""
    st = time.struct_time((2026, 8, 26, 1, 2, 3, 2, 238, 0))
    iso = feed.to_iso(st)
    # mktime 按本地时区解释，UTC 换算可能跨日；只断言秒级 ISO 格式
    assert iso[10] == "T" and iso.endswith(":03+00:00") and len(iso) == 25


def _fake_entry(guid: str, title: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=guid, link=f"https://example.com/{guid}", title=title,
        summary=f"<p>{title} 正文</p>", published_parsed=None, updated_parsed=None,
        content=[],
    )


def _fake_parse(entries: list):
    return lambda url, request_headers=None: SimpleNamespace(
        entries=entries, bozo=0, bozo_exception=None
    )


def test_fetch_source_idempotent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(feed, "RAW_FEEDS", tmp_path)
    entries = [_fake_entry("g1", "模型A发布"), _fake_entry("g2", "开源工具B")]
    monkeypatch.setattr("feedparser.parse", _fake_parse(entries))

    src = {"id": "test-src", "alias": "测试源", "url": "https://example.com/rss"}
    r1 = feed.fetch_source(src)
    assert r1["new"] == 2 and r1["stored"] == 2
    # 复抓：同 guid 全部跳过
    r2 = feed.fetch_source(src)
    assert r2["new"] == 0 and r2["stored"] == 2
    # 新条目只追加增量
    entries.append(_fake_entry("g3", "新事件C"))
    r3 = feed.fetch_source(src)
    assert r3["new"] == 1 and r3["stored"] == 3

    lines = (tmp_path / "test-src.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(lines) == 3
    import json

    item = feed.FeedItem.model_validate(json.loads(lines[0]))
    assert item.source_id == "test-src"
    assert item.title in {"模型A发布", "开源工具B"}
