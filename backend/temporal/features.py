"""SkillSnapshot 特征层：事件 + 时间闸门归一 -> 技能时间序列与窗口统计。

确定性代码，无 LLM。事实分级加权：fact=1.0 / report=0.6 / opinion=0.3。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from ..skills.resolver import SkillResolver

FACT_WEIGHTS = {"fact": 1.0, "report": 0.6, "opinion": 0.3}


@dataclass(frozen=True)
class SkillPoint:
    day: date
    weight: float
    event_type: str
    event_id: str


def _day(event: dict) -> date | None:
    raw = (event.get("published_at") or "")[:10]
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def build_series(
    events: list[dict], resolver: SkillResolver, as_of: date | None = None
) -> dict[str, list[SkillPoint]]:
    """事件流 -> {skill_id: 按日技能点序列}。as_of 非空时同时闸门事件与词典。"""
    series: dict[str, list[SkillPoint]] = {}
    for e in events:
        day = _day(e)
        if day is None:
            continue
        if as_of is not None and day > as_of:
            continue
        weight = FACT_WEIGHTS.get(e.get("fact_grade", "report"), 0.6)
        for mention in e.get("skill_mentions", []):
            hit = resolver.resolve(mention)
            if hit.skill_id is None:
                continue
            series.setdefault(hit.skill_id, []).append(
                SkillPoint(
                    day=day,
                    weight=weight,
                    event_type=e.get("event_type", ""),
                    event_id=e["event_id"],
                )
            )
    for pts in series.values():
        pts.sort(key=lambda p: p.day)
    return series


def window_stats(points: list[SkillPoint], start: date, end: date) -> dict[str, float]:
    """[start, end) 窗口统计：加权提及、原始次数、覆盖天数、事实占比。"""
    in_window = [p for p in points if start <= p.day < end]
    fact = sum(p.weight for p in in_window if p.event_type is not None)  # 加权即事实占比的权重和
    return {
        "weighted": round(sum(p.weight for p in in_window), 2),
        "raw": len(in_window),
        "days": len({p.day for p in in_window}),
        "weighted_fact": round(fact, 2),
    }


def first_seen(points: list[SkillPoint]) -> date | None:
    return points[0].day if points else None


def momentum(points: list[SkillPoint], as_of: date, horizon: int) -> dict[str, float | None]:
    """近期窗口 [as_of-H, as_of) 与基准窗口 [as_of-2H, as_of-H) 的比值。"""
    h = timedelta(days=horizon)
    recent = window_stats(points, as_of - h, as_of)
    prior = window_stats(points, as_of - 2 * h, as_of - h)
    ratio = (recent["weighted"] / prior["weighted"]) if prior["weighted"] > 0 else None
    return {"recent": recent["weighted"], "prior": prior["weighted"], "ratio": ratio}
