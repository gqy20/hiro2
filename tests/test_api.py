from fastapi.testclient import TestClient

import apps.api.main as api_main
from apps.api.main import app


def test_health_contract() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_live_does_not_require_dependencies() -> None:
    response = TestClient(app).get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_returns_503_when_not_ready(monkeypatch) -> None:
    monkeypatch.setattr(
        api_main,
        "_health_status",
        lambda: {"status": "degraded", "postgres": "unavailable", "neo4j": "ok"},
    )
    response = TestClient(app).get("/health/ready")
    assert response.status_code == 503


def test_quality_overview_contract() -> None:
    response = TestClient(app).get("/api/v1/quality/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["task_total"] == 180
    assert "error_distribution" in body


def test_dashboard_overview_contract() -> None:
    response = TestClient(app).get("/api/v1/dashboard/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["focus"]["href"] == "/jobs"
    assert len(body["queue"]) == 3


def test_evaluation_overview_contract() -> None:
    response = TestClient(app).get("/api/v1/evaluation/overview")
    assert response.status_code == 200
    assert response.json()["datasets"]


def test_dataset_overview_contract() -> None:
    response = TestClient(app).get("/api/v1/datasets/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["total_datasets"] >= 5
    assert {item["id"] for item in body["datasets"]} >= {"jd", "evaluation", "capability"}


def test_publish_job_idempotent_and_unknown_404() -> None:
    client = TestClient(app)
    # 已发布过的默认草稿：幂等返回既有 PUBLISHED 版本而非 409
    ok = client.post(
        "/api/v1/jobs/default/versions/v2/publish",
        json={"reviewer": "pytest", "note": "幂等回归"},
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["versionId"] == "ai-agent-v2"
    assert body["publishedAt"]
    assert isinstance(body["reviewActionIds"], list)
    # 复发仍幂等（发布后不可变，不得重复固化）
    again = client.post("/api/v1/jobs/default/versions/v2/publish", json={})
    assert again.status_code == 200
    assert again.json()["versionId"] == "ai-agent-v2"
    # 未知草稿 404
    missing = client.post("/api/v1/jobs/unknown/versions/v9/publish", json={})
    assert missing.status_code == 404


def test_temporal_dataset_contract_camel_top_level() -> None:
    """前端契约：/temporal/dataset 顶层键 camelCase，内层对象 snake_case。"""
    response = TestClient(app).get("/api/v1/temporal/dataset")
    assert response.status_code == 200
    body = response.json()
    assert "backtestRecords" in body
    assert "backtest_records" not in body
    for key in ("forecasts", "signals", "suggestions", "backtests"):
        assert key in body, f"缺少顶层键 {key}"
    if body["suggestions"]:
        first = body["suggestions"][0]
        # 前端渲染硬依赖：缺 evidence_ids 会导致建议页崩溃
        assert "evidence_ids" in first
        assert "suggestion_id" in first
        assert "review_status" in first
    if body["backtestRecords"]:
        assert "skill_id" in body["backtestRecords"][0]


def test_temporal_suggestion_review_unknown_id_404() -> None:
    response = TestClient(app).post(
        "/api/v1/temporal/suggestions/sug-nonexistent/review",
        json={"decision": "accepted"},
    )
    assert response.status_code == 404


def test_task_decision_unknown_id_404() -> None:
    response = TestClient(app).post(
        "/api/v1/tasks/task-nonexistent/decision",
        json={"decision": "ACCEPT"},
    )
    assert response.status_code == 404


def test_career_resume_advice() -> None:
    draft = {
        "name": "张三",
        "title": "AI 应用工程师",
        "summary": "3 年 LLM 应用开发",
        "skills": ["Python", "LangChain"],
        "experiences": [
            {
                "company": "某公司",
                "role": "后端",
                "period": "2022-2024",
                "bullets": ["做 RAG 问答 10w 日活"],
            }
        ],
        "projects": [],
        "education": [],
    }
    response = TestClient(app).post(
        "/api/v1/career/resume/advice?job_version_id=ai-agent-v2", json=draft
    )
    assert response.status_code == 200
    body = response.json()
    assert body["required_total"] >= 4 and 0 <= body["required_covered"] <= body["required_total"]
    kinds = {a["kind"] for a in body["advice"]}
    assert "coverage" in kinds  # 必备未全覆盖 -> 覆盖差建议存在
    assert body["advice"][0]["evidence"]  # 建议必须带证据


def test_career_resume_advice_unknown_job_404() -> None:
    response = TestClient(app).post(
        "/api/v1/career/resume/advice?job_version_id=nonexistent", json={}
    )
    assert response.status_code == 404


def test_career_resume_render_pdf() -> None:
    import shutil

    if not shutil.which("pandoc"):
        import pytest

        pytest.skip("CI 无 pandoc，渲染链路本地/容器验证")
    draft = {
        "name": "张三",
        "title": "AI 应用工程师",
        "skills": ["Python"],
        "experiences": [],
        "projects": [],
        "education": [],
    }
    response = TestClient(app).post("/api/v1/career/resume/render", json=draft)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content[:5] == b"%PDF-"
