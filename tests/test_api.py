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
