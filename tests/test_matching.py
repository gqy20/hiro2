"""匹配引擎测试：四档判定、必备优先、发布版本前置。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.candidates.models import CandidateProfile, EffectiveSkill  # noqa: E402
from backend.matching import engine  # noqa: E402


@pytest.fixture()
def published(monkeypatch, tmp_path):
    job = {
        "version_id": "test-v1",
        "required_skill_ids": [
            {"skill_id": "cap_04", "name": "AI Agent"},
            {"skill_id": "cap_07", "name": "Python"},
        ],
        "preferred_skill_ids": [{"skill_id": "cap_02", "name": "Prompt工程"}],
        # 与真实发布版本一致：基线证据嵌套在 evidence 下
        "evidence": {"baseline_evidence_id": "xlsx:pos_02"},
    }
    pub_dir = tmp_path / "published"
    pub_dir.mkdir()
    (pub_dir / "test-v1.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(engine, "PUBLISHED_DIR", pub_dir)
    return job


def _profile(skills: list[EffectiveSkill]) -> CandidateProfile:
    return CandidateProfile(candidate_id="c1", raw_extraction_id="c1:raw", skills=skills)


def test_match_verdicts(published):
    p = _profile(
        [
            EffectiveSkill(mention="Agent", skill_id="cap_04", proficiency="高级", years=3),
            EffectiveSkill(mention="Python", skill_id="cap_07", proficiency="初级"),
            EffectiveSkill(mention="LangChain", point_id="cap_04.工具调用"),
        ]
    )
    report = engine.match(p, "test-v1")
    verdicts = {g.name: g.verdict for g in report.gaps}
    assert verdicts["AI Agent"] == "已具备"  # 达标具备
    assert verdicts["Python"] == "部分具备"  # 初级 -> 部分
    assert verdicts["Prompt工程"] == "缺失"
    assert report.required_coverage == 0.5
    assert report.key_shortboards == ["Python"]  # 必备缺失/部分优先


def test_match_requires_published(published, monkeypatch):
    p = _profile([])
    with pytest.raises(FileNotFoundError):
        engine.match(p, "nonexistent-v9")


def test_match_report_carries_job_baseline_evidence(published):
    """必备能力的岗位依据携带基线证据，报告 evidence_ids 去重非空。"""
    p = _profile([EffectiveSkill(mention="Agent", skill_id="cap_04", proficiency="高级", years=3)])
    report = engine.match(p, "test-v1")
    required_gaps = [g for g in report.gaps if g.is_required]
    assert required_gaps and all(g.job_evidence_ids == ["xlsx:pos_02"] for g in required_gaps)
    assert report.evidence_ids == ["xlsx:pos_02"]


def test_learning_path_priority_order(published):
    p = _profile([EffectiveSkill(mention="Python", skill_id="cap_07", proficiency="中级")])
    report = engine.match(p, "test-v1")
    path = engine.learning_path(report)
    prios = [s.priority for s in path.steps]
    assert prios[0].startswith("P0")  # 必备缺失最前
    assert all(p.startswith("P0") or p.startswith("P2") for p in prios)
