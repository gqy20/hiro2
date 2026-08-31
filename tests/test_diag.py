from backend.application.diagnosis import (
    _candidate_display_name,
    _format_experience,
    _format_headline,
    _skill_evidence,
)


def test_candidate_display_name_never_falls_back_to_internal_id() -> None:
    candidate = {"candidate_id": "synth_agent_senior_02", "name": ""}

    assert _candidate_display_name(candidate) == "候选人 02"


def test_candidate_display_name_prefers_structured_name() -> None:
    candidate = {"candidate_id": "candidate_02", "name": "李同学"}

    assert _candidate_display_name(candidate) == "李同学"


def test_candidate_headline_formats_integer_years_without_decimal() -> None:
    candidate = {
        "education": "华中科技大学 计算机科学与技术 本科（2012-2016）",
        "experience_years": 8.0,
    }

    assert _format_experience(8.0) == "8 年经验"
    assert _format_headline(candidate) == (
        "华中科技大学 计算机科学与技术 本科（2012-2016） · 8 年经验"
    )


def test_skill_evidence_uses_business_source_instead_of_resolution_method() -> None:
    assert _skill_evidence({"source": "raw", "resolved_by": "dict"}) == "简历提及"
    assert _skill_evidence({"source": "correction"}) == "人工修正"


def test_build_diagnosis_attributes_job_evidence_per_gap(monkeypatch) -> None:
    """缺口携带岗位侧 JD 归因证据（确定性：JD 归一技能命中岗位证据集）。"""
    from backend.application import diagnosis
    from backend.application.diagnosis import build_diagnosis

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(diagnosis, "_EVIDENCE_INDEX", None, raising=False)
    monkeypatch.setattr(diagnosis, "_JD_SKILLS", None, raising=False)
    monkeypatch.setattr(diagnosis, "_REPO", None, raising=False)

    vm = build_diagnosis("synth_agent_senior_02", "ai-agent-v2")
    gaps = vm.report["gaps"]
    assert gaps, "应存在缺口"
    with_evidence = [g for g in gaps if g["jobEvidence"]]
    assert with_evidence, "至少一个缺口应归因到招聘 JD 证据"
    for entry in with_evidence[0]["jobEvidence"]:
        assert entry["sourceType"] == "招聘 JD"
        assert entry["excerpt"]


def test_build_diagnosis_exposes_resolved_report_evidence(monkeypatch) -> None:
    """报告 evidence_ids 解析为前端证据条目（走离线文件路径，避免依赖数据库）。"""
    from backend.application import diagnosis
    from backend.application.diagnosis import build_diagnosis

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(diagnosis, "_EVIDENCE_INDEX", None, raising=False)
    monkeypatch.setattr(diagnosis, "_REPO", None, raising=False)

    vm = build_diagnosis("synth_agent_senior_02", "ai-agent-v2")
    evidence = vm.report["evidence"]
    assert evidence, "报告应携带已解析证据"
    item = evidence[0]
    assert item["id"] == "xlsx:pos_02"
    assert item["sourceType"] == "职业标准"
    assert item["excerpt"]
