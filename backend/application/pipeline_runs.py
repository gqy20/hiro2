"""Pipeline run 列表 View Model：扫描 data/runs/<run_id>/events.jsonl。

仅聚合不写库；HR / 评委只读查看最近运行。
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

ROOT = Path(__file__).resolve().parents[2]
RUNS_DIR = ROOT / "data" / "runs"

_MAX_RUNS = 200  # 目录扫描上限，避免一次性加载过多

# component -> 流转图四阶段映射。依据各脚本 docstring 核实：
# 采集：jdcorp/jdauto/jdarchive 为 JD 采集，rssget/arxivget/dadianget/policyget 为外部源采集；
# 标准化：jdxtract 解析+词典归一，extract 事件抽取，evdedup 去重，
# resolve/skillmap 技能归一，rolemap 岗位映射；
# 证据化：evidence 证据实体层；
# 信号化：sigbuild TrendSignal，snapshotdiff JobChangeSet，leadtime/pypidl 信号对比。
# 未列入的组件（jobpub/jobver/dbimport 等发布与入库环节）归为 other，不在四步图展示。
COMPONENT_STAGE: dict[str, str] = {
    "jdcorp": "ingest",
    "jdauto": "ingest",
    "jdarchive": "ingest",
    "jdboss": "ingest",
    "rssget": "ingest",
    "arxivget": "ingest",
    "dadianget": "ingest",
    "policyget": "ingest",
    "genresume": "ingest",
    "md2res": "ingest",
    "resumeimport": "ingest",
    "jdxtract": "extract",
    "jdclean": "extract",
    "extract": "extract",
    "evdedup": "extract",
    "resolve": "extract",
    "rolemap": "extract",
    "skillmap": "extract",
    "exskill": "extract",
    "evidence": "evidence",
    "sigbuild": "signal",
    "snapshotdiff": "signal",
    "leadtime": "signal",
    "pypidl": "signal",
}


class _VM(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PipelineRunVM(_VM):
    run_id: str
    component: str
    status: str
    stage: str = "run"
    started_at: str
    finished_at: str | None = None
    duration_ms: int | None = None
    count_summary: str = ""
    error: str | None = None


class PipelineRunListVM(_VM):
    runs: list[PipelineRunVM] = Field(default_factory=list)
    total: int = 0


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _summarize_count(count: Any) -> str:
    """把 count dict 压成一行可读摘要。"""
    if not isinstance(count, dict):
        return ""
    parts: list[str] = []
    for key in ("positions", "rows", "index_rows", "items", "papers", "skills"):
        if key in count:
            parts.append(f"{count[key]} {key}")
            break
    for key, label in (
        ("capabilities", "能力"),
        ("groups", "组"),
        ("issues", "问题"),
        ("ok", "通过"),
        ("quarantined", "隔离"),
        ("orphan_files", "孤儿"),
    ):
        if key in count and key not in {"positions", "rows", "index_rows"}:
            parts.append(f"{count[key]} {label}")
            break
    return " · ".join(parts)


def _aggregate_run(run_dir: Path) -> PipelineRunVM | None:
    events_path = run_dir / "events.jsonl"
    if not events_path.is_file():
        return None
    started: dict[str, Any] | None = None
    finished: dict[str, Any] | None = None
    failed: dict[str, Any] | None = None
    for line in events_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            evt = json.loads(line)
        except json.JSONDecodeError:
            continue
        event = evt.get("event")
        if event == "started" and started is None:
            started = evt
        elif event == "finished" and finished is None:
            finished = evt
        elif event == "failed" and failed is None:
            failed = evt

    head = started or failed or finished
    if head is None:
        return None

    started_at = str(head.get("ts", ""))
    status = str(
        (failed or {}).get("status")
        or (finished or {}).get("status")
        or head.get("status", "UNKNOWN")
    )
    error: str | None = None
    if failed is not None:
        err_type = failed.get("error_type")
        err_msg = failed.get("error_message")
        if err_type or err_msg:
            error = f"{err_type}: {err_msg}" if err_type and err_msg else (err_type or err_msg)

    duration_ms: int | None = None
    start_dt = _parse_ts(started_at)
    end_dt = _parse_ts(str((finished or failed or {}).get("ts", "")))
    if start_dt and end_dt:
        duration_ms = int((end_dt - start_dt).total_seconds() * 1000)

    count = (finished or failed or {}).get("count")
    component = str(head.get("component", "unknown"))
    return PipelineRunVM(
        run_id=str(head.get("run_id", run_dir.name)),
        component=component,
        status=status.upper(),
        stage=COMPONENT_STAGE.get(component, "other"),
        started_at=started_at,
        finished_at=str((finished or failed or {}).get("ts", "")) or None,
        duration_ms=duration_ms,
        count_summary=_summarize_count(count),
        error=error,
    )


def build_pipeline_runs(limit: int = 50, since_days: int = 7) -> PipelineRunListVM:
    if not RUNS_DIR.is_dir():
        return PipelineRunListVM(runs=[], total=0)

    cutoff = datetime.now(UTC) - timedelta(days=since_days)

    run_dirs = sorted(
        (p for p in RUNS_DIR.iterdir() if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )[:_MAX_RUNS]

    runs: list[PipelineRunVM] = []
    for run_dir in run_dirs:
        vm = _aggregate_run(run_dir)
        if vm is None:
            continue
        started_dt = _parse_ts(vm.started_at)
        if started_dt and started_dt < cutoff:
            continue
        runs.append(vm)

    # total 必须是窗口内的真实总数，不能等于当前页条数
    return PipelineRunListVM(runs=runs[:limit], total=len(runs))
