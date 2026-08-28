"""JD 快照采集域：API 服务内的周期后台任务（启动即采集）。

每轮 = jdcorp runall（8 站增量，缓存幂等）→ 快照归档（当期文件拷贝
snapshots/YYYY-MM-DD/，保留每期完整视图）→ jdxtract + rolemap 增量分析
（LLM，幂等）。CLI 以独立子进程运行，失败只记日志不拖垮 API。

开关（.env / 容器环境变量）：
    HIRO2_SNAPSHOT_ENABLED=true|false   默认 false（本地开发不乱抓；
                                          compose/生产置 true 实现"启动即采集"）
    HIRO2_SNAPSHOT_INTERVAL_HOURS=24    周期
    HIRO2_SNAPSHOT_ANALYZE=true         采集后是否跑 LLM 解析映射（成本开关）
"""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORP = ROOT / "data" / "raw" / "jd" / "corp"
SNAPSHOTS = CORP / "snapshots"

# ponytail: 生产页深 5 + 全量 board 足够日级增量；缓存保证无新岗位时秒级跳过
_SNAPSHOT_CMD = [
    sys.executable,
    "scripts/jdcorp.py",
    "runall",
    "--keywords",
    "ALL",
    "--pages",
    "5",
    "--workers",
    "3",
]
_ANALYZE_CMDS = [
    [sys.executable, "scripts/jdxtract.py", "run"],
    [sys.executable, "scripts/rolemap.py", "run"],
]
_STEP_TIMEOUTS = {0: 15 * 60, 1: 4 * 3600, 2: 3600}  # 采集 / 解析 / 映射


def _log(step: str, msg: str) -> None:
    print(f"[snapshot {time.strftime('%H:%M:%S')}] {step}: {msg}", flush=True)


async def _run_step(idx: int, cmd: list[str]) -> bool:
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, cwd=ROOT, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=_STEP_TIMEOUTS.get(idx, 3600))
        tail = (out or b"").decode("utf-8", "replace").strip().splitlines()
        _log(cmd[1].split("/")[-1], tail[-1][:160] if tail else f"exit {proc.returncode}")
        return proc.returncode == 0
    except Exception as exc:  # noqa: BLE001 - 后台任务失败不冒泡
        _log(cmd[1].split("/")[-1], f"失败 {str(exc)[:120]}")
        return False


def _archive_snapshot() -> str:
    """当期 corp 文件拷贝到 snapshots/日期/（每期完整视图，重建历史用）。"""
    stamp = time.strftime("%Y-%m-%d")
    dest = SNAPSHOTS / stamp
    if dest.is_dir():
        return stamp  # 当日已归档（一天多轮只留首份）
    dest.mkdir(parents=True, exist_ok=True)
    for f in CORP.glob("*.jsonl"):
        shutil.copy(f, dest / f.name)
    return stamp


async def run_import_once() -> dict:
    """启动时后台跑一次 dbimport（幂等，不阻塞 API 就绪）。

    解决远端容器 SSH 手动导入的 FK 顺序问题——启动进程内环境完整，
    capabilities/skills/evidence 等按 dbimport 内置顺序串行导入。
    """
    cmd = [sys.executable, "scripts/dbimport.py", "run"]
    ok = await _run_step(99, cmd)  # 99 = import（不在 _STEP_TIMEOUTS 里，走默认 1h）
    _log("import", "done" if ok else "failed")
    return {"imported": ok}


async def run_snapshot_once() -> dict:
    """单轮：采集 -> 归档 -> 分析。返回指标（也用于手动触发）。"""
    started = time.time()
    ok = await _run_step(0, _SNAPSHOT_CMD)
    stamp = _archive_snapshot() if ok else "-"
    analyzed = 0
    if ok and os.getenv("HIRO2_SNAPSHOT_ANALYZE", "true").lower() in ("1", "true"):
        for i, cmd in enumerate(_ANALYZE_CMDS, start=1):
            analyzed += await _run_step(i, cmd)
    metrics = {
        "collected": ok,
        "snapshot": stamp,
        "analyzed_steps": analyzed,
        "seconds": round(time.time() - started),
    }
    _log("done", str(metrics))
    return metrics


async def snapshot_loop() -> None:
    """API lifespan 后台循环：启动 60s 后首轮，此后按周期。"""
    await asyncio.sleep(60)  # 先让 API 就绪
    while True:
        try:
            await run_snapshot_once()
        except Exception as exc:  # noqa: BLE001 - 循环永不退出
            _log("loop", f"异常 {str(exc)[:120]}")
        hours = float(os.getenv("HIRO2_SNAPSHOT_INTERVAL_HOURS", "24") or 24)
        await asyncio.sleep(max(hours, 0.5) * 3600)


def snapshot_enabled() -> bool:
    return os.getenv("HIRO2_SNAPSHOT_ENABLED", "false").lower() in ("1", "true")
