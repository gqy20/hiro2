"""学练赛证实体映射测试：证书/竞赛反查、mention 正查、等级换算、匹配证据分支。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.candidates.models import (  # noqa: E402
    CandidateProfile,
    CertificateEntry,
    EffectiveSkill,
    ProjectEntry,
)
from backend.matching import engine, xlzsz  # noqa: E402


@pytest.fixture()
def published(monkeypatch, tmp_path):
    job = {
        "version_id": "test-v1",
        "required_skill_ids": [
            {"skill_id": "cap_04", "name": "AI Agent"},
            {"skill_id": "cap_07", "name": "Python"},
        ],
        "preferred_skill_ids": [{"skill_id": "cap_02", "name": "Prompt工程"}],
        "baseline_evidence_id": "xlsx:pos_02",
    }
    pub_dir = tmp_path / "published"
    pub_dir.mkdir()
    (pub_dir / "test-v1.json").write_text(json.dumps(job, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(engine, "PUBLISHED_DIR", pub_dir)
    return job


def _profile(
    skills: list[EffectiveSkill] | None = None,
    certs: list[CertificateEntry] | None = None,
    projects: list[ProjectEntry] | None = None,
) -> CandidateProfile:
    return CandidateProfile(
        candidate_id="c1",
        raw_extraction_id="c1:raw",
        skills=skills or [],
        certificates=certs or [],
        projects=projects or [],
    )


# ---------------------------------------------------------------- 实体反查


def test_certs_for_skill():
    certs = xlzsz.certs_for_skill("cap_04")
    names = [c["name"] for c in certs]
    assert "智能体工程师认证" in names
    assert all(c["issuer"] for c in certs)  # 每条可回链颁发机构


def test_contests_for_skill():
    contests = xlzsz.contests_for_skill("cap_01")
    assert len(contests) >= 1
    assert any("讯飞" in c["name"] for c in contests)  # cap_01 -> 讯飞大模型类赛事


def test_certs_for_unknown_skill_empty():
    assert xlzsz.certs_for_skill("cap_99") == []
    assert xlzsz.contests_for_skill("cap_99") == []


# ---------------------------------------------------------------- mention 正查


def test_match_cert_mention():
    hits = xlzsz.match_cert_mention("已取得 HCIA-AI 认证，熟悉深度学习")
    assert any(h["name"] == "HCIA-AI" for h in hits)


def test_match_cert_mention_full_name():
    hits = xlzsz.match_cert_mention("持有人工智能训练师国家职业技能等级证书")
    assert any("人工智能训练师" in h["name"] for h in hits)


def test_match_contest_mention():
    hits = xlzsz.match_contest_mention("曾参加蓝桥杯全国软件和信息技术专业人才大赛获省一等奖")
    assert any("蓝桥杯" in h["name"] for h in hits)


def test_match_mention_empty_text():
    assert xlzsz.match_cert_mention("") == []
    assert xlzsz.match_contest_mention("") == []


# ---------------------------------------------------------------- 等级换算


def test_award_to_level():
    assert xlzsz.award_to_level("cahe", "国家级一等奖") == "L3"
    assert xlzsz.award_to_level("cahe", "省级二等奖") == "L1"
    assert xlzsz.award_to_level("enterprise", "冠军") == "L3"
    assert xlzsz.award_to_level("cahe", "未列出奖项") == "L1"  # 默认


def test_cert_level():
    assert xlzsz.cert_level("huawei", "hcip") == "L2"
    assert xlzsz.cert_level("osta_engineer", "高级") == "L3"
    assert xlzsz.cert_level("unknown", "初级") == "L1"


# ---------------------------------------------------------------- 学段知识点（国家职业标准）


def test_knowledge_for_skill_relevant():
    """cap_09 大数据有国标相关知识点，应返回带标准名与上下文的条目。"""
    ks = xlzsz.knowledge_for_skill("cap_09", limit=2)
    assert len(ks) >= 1
    assert ks[0]["std_name"] == "大数据工程技术人员"
    assert "大数据" in ks[0]["knowledge"]
    assert ks[0]["career_code"]  # 可回链官方标准文件


def test_knowledge_for_skill_honest_fallback():
    """cap_02 Prompt 工程在 2021 国标中无对应知识点，应诚实返空而非硬套。"""
    assert xlzsz.knowledge_for_skill("cap_02") == []


def test_knowledge_no_false_positive_short_word():
    """短词"记忆"不应误命中"长短期记忆网络"（LSTM）——关键词最小长度过滤。"""
    ks = xlzsz.knowledge_for_skill("cap_04", limit=5)
    for k in ks:
        assert "记忆网络" not in k["knowledge"]


# ---------------------------------------------------------------- 匹配引擎证据分支


def test_match_certificate_evidence(published):
    """证书命中 -> 判已具备，证据为证书名。"""
    p = _profile(certs=[CertificateEntry(name="智能体工程师认证", issuer="讯飞AI大学堂")])
    report = engine.match(p, "test-v1")
    verdicts = {g.name: g.verdict for g in report.gaps}
    assert verdicts["AI Agent"] == "已具备"
    ev = next(g for g in report.gaps if g.name == "AI Agent")
    assert "智能体工程师认证" in ev.candidate_evidence


def test_match_contest_evidence_partial(published):
    """竞赛经历（无技能直接证据）-> 缺失提升为部分具备。"""
    p = _profile(projects=[ProjectEntry(name="参加蓝桥杯全国软件和信息技术专业人才大赛")])
    report = engine.match(p, "test-v1")
    verdicts = {g.name: g.verdict for g in report.gaps}
    # 蓝桥杯映射 cap_07（Python），不映射 cap_04
    assert verdicts["Python"] == "部分具备"
    assert verdicts["AI Agent"] == "缺失"


def test_match_contest_award_evidence(published):
    """竞赛获奖 -> 部分具备，证据携带获奖等级与 award_to_level 换算。"""
    p = _profile(
        projects=[ProjectEntry(name="参加蓝桥杯全国软件和信息技术专业人才大赛", award="省级一等奖")]
    )
    report = engine.match(p, "test-v1")
    gap = next(g for g in report.gaps if g.name == "Python")
    assert gap.verdict == "部分具备"
    assert "省级一等奖" in gap.candidate_evidence
    assert "L2" in gap.candidate_evidence  # award_to_level(cahe, 省级一等奖)=L2


def test_learning_path_cites_real_certs(published):
    """学练赛证"证"段引用 CERTS.yml 真实证书名。"""
    p = _profile([EffectiveSkill(mention="Python", skill_id="cap_07", proficiency="高级")])
    report = engine.match(p, "test-v1")
    path = engine.learning_path(report)
    agent_step = next(s for s in path.steps if s.name == "AI Agent")
    assert "认证" in agent_step.certify  # 引用真实证书而非纯模板
    prompt_step = next(s for s in path.steps if s.name == "Prompt工程")
    assert "Prompt工程师认证" in prompt_step.certify


def test_learning_path_cites_real_contests(published):
    """学练赛证"赛"段引用 CONTESTS.yml 真实赛事名。"""
    p = _profile([EffectiveSkill(mention="Python", skill_id="cap_07", proficiency="高级")])
    report = engine.match(p, "test-v1")
    path = engine.learning_path(report)
    agent_step = next(s for s in path.steps if s.name == "AI Agent")
    # cap_04 有竞赛映射（挑战杯/讯飞 Skill 赛），赛段应引用真实赛事
    assert "挑战杯" in agent_step.evaluate or "讯飞" in agent_step.evaluate
