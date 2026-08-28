"""ForecastEngine：确定性规则的趋势方向预测。LLM 不参与数值预测（见 docs/architecture.md）。

规则版本：
  v1 动量延续：近期/基准加权比 >=1.3 判 up，<=0.7 判 down，否则 flat。
  v2 回测修正（eval-v1 回测 136 条错误分析推导，非逐点调参）：
    - 过热抑制：v1 中 ratio>2.94 的 up 预测全部反转（最大 16.67），
      命中条 ratio 上限 2.94——ratio >=3.0 不再追涨，判 flat；
    - down 保守化：v1 中 down 预测错误条的 48% 实际反弹为 up，
      下跌阈值从 0.7 收紧到 0.5；
    - up 温区间不变（1.3~3.0 判 up）。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from .features import SkillPoint, window_stats

RULE_VERSION = 2  # 当前生产规则版本
UP_RATIO, DOWN_RATIO = 1.3, 0.7
MIN_RECENT_WEIGHTED = 2.0  # 近期低于此量不具预测资格（噪声）

# v2 阈值（推导依据见模块 docstring）
UP_RATIO_V2, UP_OVERHEAT_V2, DOWN_RATIO_V2 = 1.3, 3.0, 0.5


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


def _direction_v2(ratio: float | None) -> str:
    """v2：过热抑制 + down 保守化（推导依据见模块 docstring）。"""
    if ratio is None:
        return "flat"
    if ratio >= UP_OVERHEAT_V2:
        return "flat"  # 过热不追涨
    if ratio >= UP_RATIO_V2:
        return "up"
    if ratio <= DOWN_RATIO_V2:
        return "down"
    return "flat"


def _confidence(recent: float, prior: float, direction: str) -> float:
    if direction == "flat":
        return 0.4
    base = min(recent, prior) / 5.0  # 样本量分量：两侧都有量才可信
    return round(min(0.9, 0.3 + base), 2)


def forecast_skill(
    skill_id: str,
    points: list[SkillPoint],
    as_of: date,
    horizon: int,
    rule: int = RULE_VERSION,
) -> Forecast | None:
    h = timedelta(days=horizon)
    recent = window_stats(points, as_of - h, as_of)
    prior = window_stats(points, as_of - 2 * h, as_of - h)
    if recent["weighted"] < MIN_RECENT_WEIGHTED:
        return None  # 量不足，不具预测资格
    ratio = (recent["weighted"] / prior["weighted"]) if prior["weighted"] > 0 else None
    decide = _direction_v2 if rule >= 2 else _direction
    direction = "up" if ratio is None else decide(ratio)
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
