"""Outbox 域单测：开关解析、退避规则与 consume_batch 重试语义（不联网）。"""

import pytest

from backend.application import outbox, outbox_worker


def test_worker_enabled_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HIRO2_OUTBOX_WORKER", raising=False)
    assert outbox_worker.outbox_worker_enabled() is False
    monkeypatch.setenv("HIRO2_OUTBOX_WORKER", "true")
    assert outbox_worker.outbox_worker_enabled() is True


def test_retry_delay_backoff_and_cap() -> None:
    assert outbox.retry_delay(1) == 60
    assert outbox.retry_delay(2) == 120
    assert outbox.retry_delay(3) == 240
    assert outbox.retry_delay(10) == 3600  # 封顶 1 小时


def test_consume_batch_retries_then_dead(monkeypatch: pytest.MonkeyPatch) -> None:
    """消费失败：attempts 未达上限回 PENDING（带退避），达上限转 FAILED 终态。

    用假连接对象模拟 outbox_events 行为，验证 SQL 状态转移语义，不依赖 PG。
    """

    class _FakeCursor:
        def __init__(self, rows: list[tuple]) -> None:
            self._rows = rows
            self.executed: list[tuple] = []

        def execute(self, sql: str, params=()) -> None:
            self.executed.append((sql, params))

        def fetchall(self) -> list[tuple]:
            return self._rows

    class _FakeConn:
        def __init__(self, rows: list[tuple]) -> None:
            self.cur = _FakeCursor(rows)

        def execute(self, sql: str, params=()):
            self.cur.execute(sql, params)
            return self.cur

        def commit(self) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    rows = [
        ("ev-1", "JobVersionPublished", "ai-agent-v2", {}, 1),  # 重试区
        ("ev-2", "JobVersionPublished", "bigdata-v2", {}, 5),  # 达上限 -> FAILED
    ]
    conn = _FakeConn(rows)

    def boom(_payload):
        raise RuntimeError("projection down")

    with monkeypatch.context() as m:
        # consume_batch 函数内 import psycopg，patch 模块属性对其生效
        m.setattr("psycopg.connect", lambda _dsn: conn)
        result = outbox.consume_batch("dsn", project=boom, max_attempts=5)
    assert result == {"processed": 0, "retried": 1, "failed": 1}
    ups = [s for s, _ in conn.cur.executed if "status='PENDING'" in s]
    dead = [s for s, _ in conn.cur.executed if "status='FAILED'" in s]
    assert len(ups) == 1 and len(dead) == 1
