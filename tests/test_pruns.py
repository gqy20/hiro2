"""pipeline_runs View Model 单测：total 口径、状态归一、stage 映射。"""

import json
from datetime import UTC, datetime

import pytest

from backend.application import pipeline_runs
from backend.application.pipeline_runs import build_pipeline_runs


def _write_run(runs_dir, run_id: str, component: str, status: str) -> None:
    run_dir = runs_dir / run_id
    run_dir.mkdir(parents=True)
    ts = datetime.now(UTC).isoformat()
    events = [
        {
            "ts": ts,
            "run_id": run_id,
            "component": component,
            "event": "started",
            "status": "RUNNING",
        },
    ]
    if status != "RUNNING":
        events.append(
            {
                "ts": ts,
                "run_id": run_id,
                "component": component,
                "event": "finished",
                "status": status,
            }
        )
    (run_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(e) for e in events), encoding="utf-8"
    )


@pytest.fixture
def runs_dir(tmp_path, monkeypatch):
    d = tmp_path / "runs"
    d.mkdir()
    monkeypatch.setattr(pipeline_runs, "RUNS_DIR", d)
    return d


def test_total_reflects_window_not_page_size(runs_dir):
    for i in range(5):
        _write_run(runs_dir, f"20260828T10000{i}-aaa{i:02d}", "jobpub", "SUCCEEDED")
    result = build_pipeline_runs(limit=2)
    assert len(result.runs) == 2
    assert result.total == 5


def test_status_normalized_uppercase(runs_dir):
    _write_run(runs_dir, "20260828T100000-bbb001", "dbimport", "succeeded")
    result = build_pipeline_runs(limit=10)
    assert result.runs[0].status == "SUCCEEDED"


def test_stage_mapping(runs_dir):
    _write_run(runs_dir, "20260828T100001-ccc001", "jdcorp", "SUCCEEDED")
    _write_run(runs_dir, "20260828T100002-ccc002", "sigbuild", "SUCCEEDED")
    _write_run(runs_dir, "20260828T100003-ccc003", "jobpub", "SUCCEEDED")
    by_component = {r.component: r.stage for r in build_pipeline_runs(limit=10).runs}
    assert by_component["jdcorp"] == "ingest"
    assert by_component["sigbuild"] == "signal"
    assert by_component["jobpub"] == "other"
