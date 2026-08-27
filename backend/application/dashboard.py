"""Dashboard aggregation for the recruiting workspace."""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from pydantic import BaseModel, Field

from .service import ApplicationService
from .temporal_vm import build_tasks, build_temporal

ROOT = Path(__file__).resolve().parents[2]


def _capability_names() -> dict[str, str]:
    path = ROOT / "data" / "processed" / "capability-matrix" / "capabilities.json"
    if not path.is_file():
        return {}
    return {
        item["capability_id"]: item["name"]
        for item in json.loads(path.read_text(encoding="utf-8")).get("capabilities", [])
    }


class DashboardItem(BaseModel):
    href: str
    label: str
    value: int
    meta: str


class DashboardOverview(BaseModel):
    source: str = "processed"
    focus: dict[str, str]
    queue: list[DashboardItem] = Field(default_factory=list)
    status: dict[str, str]
    jobs: list[dict[str, str | int]] = Field(default_factory=list)
    activities: list[dict[str, str]] = Field(default_factory=list)
    metrics: dict[str, int] = Field(default_factory=dict)
    trends: list[dict[str, object]] = Field(default_factory=list)
    attention: list[dict[str, str | int]] = Field(default_factory=list)


def build_dashboard() -> DashboardOverview:
    svc = ApplicationService()
    update = svc.job_update()
    emerging = svc.emerging_jobs()
    task_list = build_tasks()
    temporal = build_temporal()
    pending_updates = sum(item.status in ("reviewing", "needs_evidence") for item in update.changes)
    return DashboardOverview(
        focus={
            "title": update.context["jobTitle"],
            "stage": "审核能力变化",
            "next": "完成审核后发布新版本",
            "href": "/jobs",
            "pending": str(pending_updates),
            "summary": (
                f"{len(update.changes)} 项能力变化，来自 {update.summary['validSamples']} 条样本。"
            ),
        },
        queue=[
            DashboardItem(
                href="/new-jobs",
                label="新岗位待审",
                value=len(emerging.candidates),
                meta=f"{emerging.candidates[0].source_count if emerging.candidates else 0} 条来源",
            ),
            DashboardItem(
                href="/jobs",
                label="岗位更新待审",
                value=pending_updates,
                meta=f"{update.summary['validSamples']} 条样本",
            ),
            DashboardItem(
                href="/tasks",
                label="审核任务",
                value=task_list.pending,
                meta=f"{task_list.total - task_list.pending} 条已完成",
            ),
        ],
        status={
            "data_as_of": update.context["timeWindow"].split(" vs ")[-1].split(":")[-1],
            "backtests": str(len(temporal.backtests)),
            "pending_reviews": str(pending_updates),
        },
        jobs=[
            {
                "title": update.context["jobTitle"],
                "version": update.context["targetVersion"],
                "status": "待审核",
                "pending": pending_updates,
                "href": "/jobs",
            }
        ],
        activities=[
            {"label": "岗位变化分析完成", "detail": f"{len(update.changes)} 项能力变化待审核"},
            {"label": "新岗位候选生成", "detail": f"{len(emerging.candidates)} 个候选岗位"},
            {"label": "回测运行完成", "detail": f"{len(temporal.backtests)} 个时间窗口"},
        ],
        metrics={
            "positions": 1,
            "needs_update": int(pending_updates > 0),
            "pending_changes": pending_updates,
            "published_versions": 1,
        },
        trends=_build_trends(temporal),
        attention=[
            {
                "title": update.context["jobTitle"],
                "detail": f"{pending_updates} 项能力变化待审核",
                "href": "/jobs",
            },
            {"title": "AI Agent 工程师", "detail": "新岗位定义待确认", "href": "/new-jobs"},
        ],
    )


def _build_trends(temporal) -> list[dict[str, object]]:
    """Aggregate real AI-role JD mentions into monthly demand-share series."""
    path = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
    monthly: dict[str, Counter[str]] = defaultdict(Counter)
    if not path.is_file():
        return []
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if not row.get("is_ai_role") or not row.get("publish_date"):
            continue
        month = str(row["publish_date"])[:7]
        for item in row.get("resolved") or []:
            skill_id = item.get("skill_id") if isinstance(item, dict) else None
            if skill_id:
                monthly[month][str(skill_id)] += 1
    months = sorted(monthly)
    totals = {month: sum(counts.values()) for month, counts in monthly.items()}
    skills: Counter[str] = Counter()
    for counts in monthly.values():
        skills.update(counts)
    rows: list[dict[str, object]] = []
    names = _capability_names()
    for skill_id, _ in skills.most_common(3):
        rows.append(
            {
                "skill_id": skill_id,
                "label": names.get(skill_id, skill_id),
                "months": months,
                "values": [
                    round(monthly[month][skill_id] / max(totals[month], 1) * 100, 2)
                    for month in months
                ],
                "sample_counts": [totals[month] for month in months],
            }
        )
    return rows
