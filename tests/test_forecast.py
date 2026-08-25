"""特征层与预测引擎测试：窗口统计、方向规则、时间闸门。"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.temporal.features import SkillPoint, build_series, window_stats  # noqa: E402
from backend.temporal.forecast import forecast_skill, realized_direction  # noqa: E402

AS_OF = date(2026, 6, 1)


def mk(days: list[date], weight: float = 1.0) -> list[SkillPoint]:
    return [
        SkillPoint(day=d, weight=weight, event_type="model_release", event_id=f"e{i}")
        for i, d in enumerate(days)
    ]


def span(start: date, step: int, count: int) -> list[date]:
    return [start + timedelta(days=i * step) for i in range(count)]


def test_window_stats_aggregates() -> None:
    points = mk([date(2026, 1, 1), date(2026, 1, 2), date(2026, 2, 10)])
    w1 = window_stats(points, date(2026, 1, 1), date(2026, 1, 31))
    assert w1["raw"] == 2 and abs(w1["weighted"] - 2.0) < 1e-6 and w1["days"] == 2
    assert window_stats(points, date(2026, 2, 1), date(2026, 3, 1))["raw"] == 1


def test_direction_rules() -> None:
    # 近期窗口 [05-02, 06-01)，基准窗口 [04-02, 05-02)
    prior_win = span(date(2026, 4, 3), 5, 5)  # 5 次，末次 04-23
    rising = mk(prior_win + span(date(2026, 5, 3), 3, 10))  # 近期 10 次（05-03~05-30）-> 比值 2.0
    f = forecast_skill("cap_x", rising, AS_OF, 30)
    assert f is not None and f.direction == "up"

    falling = mk(span(date(2026, 4, 3), 2, 12) + span(date(2026, 5, 3), 10, 3))  # 12 -> 3
    f2 = forecast_skill("cap_x", falling, AS_OF, 30)
    assert f2 is not None and f2.direction == "down"

    flat = mk(prior_win + span(date(2026, 5, 3), 5, 5))  # 5 -> 5
    f3 = forecast_skill("cap_x", flat, AS_OF, 30)
    assert f3 is not None and f3.direction == "flat"

    assert forecast_skill("cap_x", mk([date(2026, 5, 15)]), AS_OF, 30) is None  # 量不足


def test_realized_direction_matches_future_window() -> None:
    recent = span(date(2026, 5, 3), 5, 5)  # [05-02, 06-01) 5 次
    future_up = mk(recent + span(date(2026, 6, 3), 4, 9))  # 未来 9 次 -> up
    assert realized_direction(future_up, AS_OF, 30) == "up"
    future_flat = mk(recent + span(date(2026, 6, 3), 5, 5))  # 5 -> 5 -> flat
    assert realized_direction(future_flat, AS_OF, 30) == "flat"
    future_down = mk(recent + span(date(2026, 6, 3), 12, 2))  # 5 -> 2 -> down
    assert realized_direction(future_down, AS_OF, 30) == "down"
    assert realized_direction(mk([]), AS_OF, 30) is None


def test_build_series_gates_events_and_dictionary() -> None:
    """as_of 之后的事件与词典习得词都必须被闸掉（防泄漏核心测试）。"""
    from backend.skills.resolver import EarnedAlias, SkillEntry, SkillResolver

    entries = [SkillEntry(capability_id="cap_04", name="AI Agent", aliases=("Agent",), points=())]
    earned = [
        EarnedAlias(
            mention="MCP工具",
            capability_id="cap_04",
            point_name="MCP",
            effective_from=date(2026, 6, 15),
        )
    ]
    events = [
        {
            "event_id": "e1",
            "published_at": "2026-06-01T00:00:00",
            "fact_grade": "fact",
            "event_type": "model_release",
            "skill_mentions": ["Agent", "MCP工具"],
        },
        {
            "event_id": "e2",
            "published_at": "2026-07-01T00:00:00",
            "fact_grade": "fact",
            "event_type": "model_release",
            "skill_mentions": ["Agent", "MCP工具"],
        },
    ]
    # 站在 6-10：e2 在未来被闸；MCP工具首见 6-15 在未来被闸
    r = SkillResolver(entries, 1, earned, as_of=date(2026, 6, 10))
    assert len(build_series(events, r, as_of=date(2026, 6, 10)).get("cap_04", [])) == 1
    # 站在 6-20：e1 的 MCP工具 已可用，e2 仍被闸
    r2 = SkillResolver(entries, 1, earned, as_of=date(2026, 6, 20))
    assert len(build_series(events, r2, as_of=date(2026, 6, 20)).get("cap_04", [])) == 2
    # 不带闸门：全部进入
    r3 = SkillResolver(entries, 1, earned)
    assert len(build_series(events, r3).get("cap_04", [])) == 4
