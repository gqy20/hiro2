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
