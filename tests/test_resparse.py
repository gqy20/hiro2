from backend.skills.resolver import load_resolver
from scripts.resparse import _deterministic_extraction


def test_deterministic_resume_fallback_extracts_known_skills_and_years() -> None:
    raw = _deterministic_extraction(
        "5 年开发经验，熟悉 Python、RAG、LangGraph 和 PostgreSQL，本科学历。",
        load_resolver(),
    )
    mentions = {item["mention"] for item in raw.skills}
    assert raw.experience_years == 5
    assert raw.education == "本科"
    assert {"Python", "RAG"} <= mentions
