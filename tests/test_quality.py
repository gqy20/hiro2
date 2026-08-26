import backend.application.quality as quality
from backend.application.quality import QualityOverview, build_quality_overview


def test_quality_overview_uses_frozen_evalset() -> None:
    overview = build_quality_overview()
    assert overview.task_total == 180
    assert overview.task_resolved == 0
    assert overview.completion_rate == 0
    assert overview.dual_review_rate is None


def test_quality_overview_has_explicit_missing_data_status() -> None:
    overview = build_quality_overview()
    assert overview.data_quality["response_time"] == "unavailable"


def test_quality_overview_prefers_database_when_configured(monkeypatch) -> None:
    expected = QualityOverview(source="postgres", task_total=1)
    monkeypatch.setattr(quality, "_build_postgres_overview", lambda _dsn: expected)
    assert build_quality_overview("postgresql://example").source == "postgres"
