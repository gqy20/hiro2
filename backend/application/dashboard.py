"""Dashboard aggregation for the recruiting workspace."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .service import ApplicationService
from .temporal_vm import build_tasks, build_temporal


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
    )
