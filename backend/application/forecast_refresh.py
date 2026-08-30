"""forecast_refresh: 实时预测定时刷新（时间情报 -> 学练段前瞻反馈的供数端）。

职责：周期性重跑 livcast（实时预测）+ predsnap（合并快照），刷新
  data/processed/temporal/prediction-context.json。诊断在查看时实时读该快照，
  因此刷新后求职者立刻看到最新趋势，无需重新匹配。

开关与周期（对齐 snapshot.py 模式）：
    HIRO2_FORECAST_REFRESH_ENABLED=true|false    默认 false（本地不乱跑；生产/容器开启）
    HIRO2_FORECAST_REFRESH_INTERVAL_HOURS=24     周期，默认每天一次
                                                 （预测为确定性计算、无 LLM 成本，日刷无负担；
                                                  事件侧若按日入库则日刷刚好跟上）

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

_REFRESH_CMDS = [
    [sys.executable, "scripts/livcast.py", "run"],
    [sys.executable, "scripts/predsnap.py", "run", "--source", "live"],
]
_STEP_TIMEOUTS = {0: 15 * 60, 1: 5 * 60}  # 实时预测 / 快照合并


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
    """单轮：实时预测 -> 合并快照。返回步骤结果（也用于手动触发）。"""
    started = time.time()
    ok_live = await _run_step(0, _REFRESH_CMDS[0])
    ok_snap = await _run_step(1, _REFRESH_CMDS[1]) if ok_live else False
    _log(f"本轮{'完成' if ok_snap else '失败'} 耗时 {time.time() - started:.0f}s")
    return {"livcast": ok_live, "predsnap": ok_snap}


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
