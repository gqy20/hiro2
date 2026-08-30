"""forecast_refresh 定时刷新模块测试：开关逻辑 + 刷新命令编排。"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application import forecast_refresh as fr  # noqa: E402


def test_forecast_refresh_enabled_flag(monkeypatch):
    """默认关闭（本地不乱跑）；env 置 true 时开启。"""
    monkeypatch.delenv("HIRO2_FORECAST_REFRESH_ENABLED", raising=False)
    assert fr.forecast_refresh_enabled() is False
    monkeypatch.setenv("HIRO2_FORECAST_REFRESH_ENABLED", "true")
    assert fr.forecast_refresh_enabled() is True
    monkeypatch.setenv("HIRO2_FORECAST_REFRESH_ENABLED", "false")
    assert fr.forecast_refresh_enabled() is False


def test_refresh_commands_pipeline():
    """刷新链 = 事件采集（rssget + extract）-> livcast（实时预测）-> predsnap（快照）。"""
    assert _ingest_has("rssget.py")
    assert _ingest_has("extract.py")
    assert len(fr._FORECAST_CMDS) == 2
    assert "livcast.py" in fr._FORECAST_CMDS[0][1]
    assert "predsnap.py" in fr._FORECAST_CMDS[1][1]
    assert fr._FORECAST_CMDS[1][-2:] == ["--source", "live"]


def _ingest_has(script: str) -> bool:
    return any(script in c[1] for c in fr._INGEST_CMDS)


def test_refresh_interval_env_documented():
    """周期可配（默认每天），防止写死。"""
    src = Path(fr.__file__).read_text(encoding="utf-8")
    assert "HIRO2_FORECAST_REFRESH_INTERVAL_HOURS" in src
    assert '"24"' in src  # 默认每天一次
