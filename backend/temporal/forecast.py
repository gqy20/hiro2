"""ForecastEngine v1：确定性规则的趋势方向预测（rule_version=1）。

规则：方向延续（momentum persistence）。
- 预测：近期窗口 / 基准窗口 的加权提及比 >=1.3 判 up，<=0.7 判 down，否则 flat。
- 置信度：样本量与趋势一致性的简单组合，只作排序参考。
LLM 不参与数值预测（见 docs/architecture.md LLM 边界）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .features import SkillPoint, window_stats

RULE_VERSION = 1
UP_RATIO, DOWN_RATIO = 1.3, 0.7
MIN_RECENT_WEIGHTED = 2.0  # 近期低于此量不具预测资格（噪声）


@dataclass(frozen=True)
class Forecast:
    skill_id: str
    as_of: date
    horizon_days: int
    direction: str  # up | flat | down
    recent: float
    prior: float
    confidence: float


def _direction(ratio: float | None) -> str:
    if ratio is None:
        return "flat"
    if ratio >= UP_RATIO:
        return "up"
    if ratio <= DOWN_RATIO:
        return "down"
    return "flat"


def _confidence(recent: float, prior: float, direction: str) -> float:
    if direction == "flat":
        return 0.4
    base = min(recent, prior) / 5.0  # 样本量分量：两侧都有量才可信
    return round(min(0.9, 0.3 + base), 2)


def forecast_skill(
    skill_id: str, points: list[SkillPoint], as_of: date, horizon: int
) -> Forecast | None:
    h = timedelta(days=horizon)
    recent = window_stats(points, as_of - h, as_of)
    prior = window_stats(points, as_of - 2 * h, as_of - h)
    if recent["weighted"] < MIN_RECENT_WEIGHTED:
        return None  # 量不足，不具预测资格
    ratio = (recent["weighted"] / prior["weighted"]) if prior["weighted"] > 0 else None
    direction = "up" if ratio is None else _direction(ratio)
    # 基准窗口为空但近期有量：视为新涌现（up），置信度受单边限制
    if ratio is None:
        return Forecast(skill_id, as_of, horizon, "up", recent["weighted"], prior["weighted"], 0.35)
    return Forecast(
        skill_id,
        as_of,
        horizon,
        direction,
        recent["weighted"],
        prior["weighted"],
        _confidence(recent["weighted"], prior["weighted"], direction),
    )


def realized_direction(points: list[SkillPoint], as_of: date, horizon: int) -> str | None:
    """后验方向：[as_of, as_of+H) 对 [as_of-H, as_of) 的比值。无任何数据返回 None。"""
    h = timedelta(days=horizon)
    future = window_stats(points, as_of, as_of + h)
    recent = window_stats(points, as_of - h, as_of)
    if future["weighted"] <= 0 and recent["weighted"] <= 0:
        return None
    if recent["weighted"] <= 0:
        return "up"  # 从无到有
    ratio = future["weighted"] / recent["weighted"]
    return _direction(ratio)
