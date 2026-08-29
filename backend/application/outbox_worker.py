"""Outbox 常驻消费 worker（B-T4.5）：发布事件 -> Neo4j 投影自动一致。

环境变量：
    HIRO2_OUTBOX_WORKER=true|false     默认 false（本地无 PG/Neo4j 不启动）
    HIRO2_OUTBOX_INTERVAL_SECONDS=30   轮询周期
行为：API lifespan 启动 30s 后进入循环；单轮消费异常只记日志不退出
（模式同 backend/application/snapshot.py 的 snapshot_loop）。
"""

from __future__ import annotations

import asyncio
import os
import time

from backend.application.outbox import consume_batch


def outbox_worker_enabled() -> bool:
    return os.getenv("HIRO2_OUTBOX_WORKER", "false").lower() in ("1", "true")


async def outbox_worker_loop() -> None:
    """轮询 outbox_events，消费 JobVersionPublished -> 投影 Neo4j。"""
    dsn = os.getenv("DATABASE_URL", "")
    await asyncio.sleep(30)  # 先让 API 就绪
    while True:
        try:
            result = await asyncio.to_thread(consume_batch, dsn)
            if any(result.values()):
                print(f"[outbox] {result}", flush=True)
        except Exception as exc:  # noqa: BLE001 - 循环永不退出
            print(f"[outbox] loop 异常 {str(exc)[:120]}", flush=True)
        interval = float(os.getenv("HIRO2_OUTBOX_INTERVAL_SECONDS", "30") or 30)
        await asyncio.sleep(max(interval, 5))


def _now_ms() -> int:
    return int(time.time() * 1000)
