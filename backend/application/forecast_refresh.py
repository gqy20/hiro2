"""forecast_refresh: 时间情报定时刷新链（事件采集 -> 实时预测 -> 快照，供学练段前瞻反馈）。

职责：周期性跑完整链路，刷新 data/processed/temporal/prediction-context.json。
诊断在查看时实时读该快照，因此刷新后求职者立刻看到最新趋势，无需重新匹配。

完整链（对齐：事件采集与预测同一任务、正确顺序，避免预测基于陈旧事件）：
    rssget fetch             抓 RSS 实时源 -> raw/feeds/（尽力而为）
    extract feeds --days N   RSS 条目增量抽取进 events.jsonl（LLM，幂等，尽力而为）
    livcast run              实时预测（读 events.jsonl，确定性）
    predsnap run --source live  合并预测快照（学练段消费）
  前两步尽力而为（失败不阻塞）；预测 + 快照必定执行（用现有事件）。
  extract 用 --days 增量窗口限定 LLM 成本，且幂等跳过已抽条目。

开关与周期（对齐 snapshot.py 模式）：
    HIRO2_FORECAST_REFRESH_ENABLED=true|false    默认 false（本地不乱跑；生产/容器开启）
    HIRO2_FORECAST_REFRESH_INTERVAL_HOURS=24     周期，默认每天一次（预测确定性、无 LLM 成本；
                                                 事件抽取成本由 --days 增量窗口限定）
    HIRO2_FORECAST_REFRESH_EXTRACT_DAYS=2        事件抽取增量窗口（略大于周期以补漏）

运行形态：API lifespan 启动 60s 后首轮（等导入就绪），此后按周期；循环永不退出。
边界：只刷新预测快照（信息性前瞻信号），不改岗位版本、不绕过审核。
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# 完整链：事件采集（尽力而为）-> 实时预测 -> 快照（必执行）。索引即 _STEP_TIMEOUTS 键。
_INGEST_CMDS = [
    [sys.executable, "scripts/rssget.py", "fetch"],
    # extract feeds 的 --days 在运行时按 env 填充（增量窗口限 LLM 成本）
    [sys.executable, "scripts/extract.py", "feeds"],
]
_FORECAST_CMDS = [
    [sys.executable, "scripts/livcast.py", "run"],
    [sys.executable, "scripts/predsnap.py", "run", "--source", "live"],
]
_STEP_TIMEOUTS = {
    0: 15 * 60,  # rssget 抓取
    1: 30 * 60,  # extract feeds（LLM 抽取，预留长些）
    2: 15 * 60,  # livcast 实时预测
    3: 5 * 60,  # predsnap 快照合并
}


def forecast_refresh_enabled() -> bool:
    return os.getenv("HIRO2_FORECAST_REFRESH_ENABLED", "false").lower() in ("1", "true")


def _log(msg: str) -> None:
    print(f"[forecast-refresh {time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def _run_step(idx: int, cmd: list[str]) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=ROOT, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=_STEP_TIMEOUTS.get(idx, 3600))
        tail = (out or b"").decode("utf-8", "replace").strip().splitlines()
        _log(f"{cmd[1].split('/')[-1]}: {tail[-1][:160] if tail else f'exit {proc.returncode}'}")
        return proc.returncode == 0
    except Exception as exc:  # noqa: BLE001 - 后台任务失败不冒泡
        _log(f"{cmd[1].split('/')[-1]} 失败 {str(exc)[:120]}")
        return False


async def run_forecast_refresh_once() -> dict:
    """单轮：事件采集（尽力而为）-> 实时预测 -> 快照。返回步骤结果（也用于手动触发）。

    事件采集失败不阻塞预测：预测 + 快照用现有事件照常执行。
    """
    started = time.time()
    # 事件采集（尽力而为）：抓 RSS -> 增量抽取进 events.jsonl
    ok_rss = await _run_step(0, _INGEST_CMDS[0])
    extract_days = os.getenv("HIRO2_FORECAST_REFRESH_EXTRACT_DAYS", "2") or "2"
    ok_extract = await _run_step(1, [*_INGEST_CMDS[1], "--days", extract_days])
    if not (ok_rss and ok_extract):
        _log("事件采集部分失败，预测改用现有事件照常执行")
    # 实时预测 + 快照（必执行）
    ok_live = await _run_step(2, _FORECAST_CMDS[0])
    ok_snap = await _run_step(3, _FORECAST_CMDS[1]) if ok_live else False
    _log(f"本轮{'完成' if ok_snap else '失败'} 耗时 {time.time() - started:.0f}s")
    return {"rssget": ok_rss, "extract": ok_extract, "livcast": ok_live, "predsnap": ok_snap}


async def forecast_refresh_loop() -> None:
    """API lifespan 后台循环：启动 60s 后首轮，此后按周期刷新。"""
    await asyncio.sleep(60)  # 先让 API 与数据导入就绪
    while True:
        try:
            await run_forecast_refresh_once()
        except Exception as exc:  # noqa: BLE001 - 循环永不退出
            _log(f"异常 {str(exc)[:120]}")
        hours = float(os.getenv("HIRO2_FORECAST_REFRESH_INTERVAL_HOURS", "24") or 24)
        await asyncio.sleep(max(hours, 0.5) * 3600)
