"""Quality dashboard view model built from review and evaluation artifacts."""

from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "evaluation" / "samples"
REVIEW_ACTIONS = ROOT / "data" / "processed" / "review" / "review-actions.jsonl"


class QualityOverview(BaseModel):
    source: str = "file"
    dataset_version: str = ""
    task_total: int = 0
    task_resolved: int = 0
    completion_rate: float = 0.0
    dual_review_rate: float | None = None
    avg_response_days: float | None = None
    error_distribution: dict[str, int] = Field(default_factory=dict)
    data_quality: dict[str, str] = Field(default_factory=dict)


def _task_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for name in ("role-mapping.csv", "domain-judgment.csv", "event-extraction.csv"):
        path = SAMPLES / name
        if not path.is_file():
            continue
        with path.open(encoding="utf-8-sig", newline="") as fh:
            rows.extend(csv.DictReader(fh))
    return rows


def _resolved(row: dict[str, str]) -> bool:
    return any("?" in key and value.strip() for key, value in row.items())


def _actions() -> list[dict[str, Any]]:
    if not REVIEW_ACTIONS.is_file():
        return []
    lines = REVIEW_ACTIONS.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line]


def _response_days(actions: list[dict[str, Any]]) -> float | None:
    values: list[float] = []
    for action in actions:
        created = action.get("task_created_at")
        submitted = action.get("created_at")
        if not created or not submitted:
            continue
        try:
            start = datetime.fromisoformat(str(created).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(submitted).replace("Z", "+00:00"))
            values.append(max(0.0, (end - start).total_seconds() / 86400))
        except ValueError:
            continue
    return round(sum(values) / len(values), 2) if values else None


def _build_file_overview() -> QualityOverview:
    rows = _task_rows()
    resolved = sum(_resolved(row) for row in rows)
    actions = _actions()
    by_task: dict[str, set[str]] = {}
    errors: dict[str, int] = {}
    for action in actions:
        task_id = str(action.get("task_id", ""))
        reviewer = str(action.get("reviewer", ""))
        if task_id:
            by_task.setdefault(task_id, set()).add(reviewer)
        error_type = action.get("error_type")
        if error_type:
            errors[str(error_type)] = errors.get(str(error_type), 0) + 1

    reviewed_tasks = [reviewers for reviewers in by_task.values() if reviewers]
    dual = (
        sum(len(reviewers) >= 2 for reviewers in reviewed_tasks) / len(reviewed_tasks)
        if reviewed_tasks
        else None
    )
    manifest_path = SAMPLES / "manifest.json"
    dataset_version = ""
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        dataset_version = str(manifest.get("dataset_version", ""))

    return QualityOverview(
        source="file",
        dataset_version=dataset_version,
        task_total=len(rows),
        task_resolved=resolved,
        completion_rate=round(resolved / len(rows), 3) if rows else 0.0,
        dual_review_rate=round(dual, 3) if dual is not None else None,
        avg_response_days=_response_days(actions),
        error_distribution=dict(sorted(errors.items(), key=lambda item: (-item[1], item[0]))),
        data_quality={
            "completion": "available" if rows else "unavailable",
            "dual_review": "available" if reviewed_tasks else "unavailable",
            "response_time": "available" if _response_days(actions) is not None else "unavailable",
            "errors": "available" if errors else "unavailable",
        },
    )


def _build_postgres_overview(dsn: str) -> QualityOverview:
    import psycopg

    with psycopg.connect(dsn) as conn:
        task_total, task_resolved = conn.execute(
            """
            SELECT count(*)::int,
                   count(*) FILTER (WHERE status = 'RESOLVED')::int
            FROM review_tasks
            """
        ).fetchone()
        dual_total, dual_resolved = conn.execute(
            """
            SELECT count(*) FILTER (WHERE t.needs_dual_review)::int,
                   count(*) FILTER (
                       WHERE t.needs_dual_review
                         AND (SELECT count(DISTINCT a.reviewer)
                              FROM review_actions a WHERE a.task_id = t.task_id) >= 2
                   )::int
            FROM review_tasks t
            """
        ).fetchone()
        avg_response = conn.execute(
            """
            SELECT avg(EXTRACT(EPOCH FROM (a.created_at - t.created_at)) / 86400.0)
            FROM review_actions a JOIN review_tasks t ON t.task_id = a.task_id
            """
        ).fetchone()[0]
        errors = conn.execute(
            """
            SELECT error_type, count(*)::int
            FROM review_actions
            WHERE error_type IS NOT NULL AND error_type <> ''
            GROUP BY error_type ORDER BY count(*) DESC, error_type
            """
        ).fetchall()
        dataset_version = conn.execute(
            "SELECT coalesce(max(dataset_version), '') FROM review_tasks"
        ).fetchone()[0]

    return QualityOverview(
        source="postgres",
        dataset_version=str(dataset_version or ""),
        task_total=task_total,
        task_resolved=task_resolved,
        completion_rate=round(task_resolved / task_total, 3) if task_total else 0.0,
        dual_review_rate=round(dual_resolved / dual_total, 3) if dual_total else None,
        avg_response_days=round(float(avg_response), 2) if avg_response is not None else None,
        error_distribution={str(name): count for name, count in errors},
        data_quality={
            "completion": "available",
            "dual_review": "available" if dual_total else "unavailable",
            "response_time": "available" if avg_response is not None else "unavailable",
            "errors": "available" if errors else "unavailable",
        },
    )


def build_quality_overview(dsn: str | None = None) -> QualityOverview:
    """Use PostgreSQL as the fact source; retain file mode for offline development."""
    if dsn:
        try:
            return _build_postgres_overview(dsn)
        except Exception:
            pass
    return _build_file_overview()
