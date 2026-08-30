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


def test_award_normalization():
    """简历获奖措辞多变，归一后再查表，避免同义措辞落回默认 L1。"""
    assert xlzsz.award_to_level("cahe", "省一等奖") == "L2"  # 缺"级"
    assert xlzsz.award_to_level("cahe", "国家一等奖") == "L3"  # 缺"级"
    assert xlzsz.award_to_level("cahe", "国二") == "L2"  # 极简写法 -> 国家级二等奖 -> L2？
    assert xlzsz.award_to_level("cahe", "省一") == "L2"
    assert xlzsz._normalize_award("全国三等奖") == "国家级三等奖"
    assert xlzsz._normalize_award("冠军") == "冠军"  # 企业奖无作用域前缀，原样返回


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


def test_skill_points_for_skill():
    """国标不覆盖的能力域，用自身技能点作为学段第二层回退。"""
    pts = xlzsz.skill_points_for_skill("cap_04")
    assert "MCP" in pts and "工具调用" in pts
    assert xlzsz.skill_points_for_skill("cap_08") == []  # 无技能点的能力域返空


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
    """学练赛证"赛"段引用真实赛事；注入固定 as_of 保证确定性。"""
    from datetime import date

    p = _profile([EffectiveSkill(mention="Python", skill_id="cap_07", proficiency="高级")])
    report = engine.match(p, "test-v1")
    path = engine.learning_path(report, as_of=date(2026, 8, 31))
    agent_step = next(s for s in path.steps if s.name == "AI Agent")
    # cap_04 有竞赛映射（可报名赛事或常设精选），赛段应引用真实赛事而非纯模板
    assert agent_step.evaluate != "在项目复盘中自评 AI Agent 的独立完成度"
    assert agent_step.contests  # 有结构化赛事卡片


# ---------------------------------------------------------------- 竞赛时间维度


def test_race_status_classification():
    """赛事时间状态分类：正在报名/即将截止/进行中/已结束/时间未知。"""
    from datetime import date

    as_of = date(2026, 8, 31)
    assert (
        xlzsz.race_status({"register_end": "2026-09-30", "final_end": "2026-11-01"}, as_of)
        == "正在报名"
    )
    # 10 天内 -> 即将截止
    assert (
        xlzsz.race_status({"register_end": "2026-09-10", "final_end": "2026-10-01"}, as_of)
        == "即将截止"
    )
    # 报名截止但未完赛 -> 进行中
    assert (
        xlzsz.race_status({"register_end": "2026-08-01", "final_end": "2026-09-15"}, as_of)
        == "进行中"
    )
    assert (
        xlzsz.race_status({"register_end": "2026-07-01", "final_end": "2026-08-01"}, as_of)
        == "已结束"
    )
    assert xlzsz.race_status({"register_end": None}, as_of) == "时间未知"
    assert xlzsz.race_status({}, as_of) == "时间未知"


def test_open_contests_for_skill_actionable():
    """可报名赛事带截止日与剩余天数，按紧急度升序。"""
    from datetime import date

    as_of = date(2026, 8, 31)
    oc = xlzsz.open_contests_for_skill("cap_01", as_of, limit=3)
    assert oc, "cap_01 应有正在报名的赛事"
    for c in oc:
        assert c["status"] in ("正在报名", "即将截止")
        assert c["register_end"]
        assert isinstance(c["days_left"], int) and c["days_left"] >= 0
    # 按剩余天数升序（最紧急在前）
    days = [c["days_left"] for c in oc]
    assert days == sorted(days)


def test_open_contests_filters_placeholder_dates():
    """截止日超 365 天的占位/长期挂载赛事（如 2099-12-31）不进可报名推荐。"""
    from datetime import date

    as_of = date(2026, 8, 31)
    for cap in ("cap_01", "cap_06", "cap_09"):
        for c in xlzsz.open_contests_for_skill(cap, as_of, limit=5):
            assert c["days_left"] <= 365, f"{c['name']} 截止日过远，疑似占位数据"


# ---------------------------------------------------------------- 预测信号挂钩


def test_prediction_for_skill_rising():
    """预测上升（高置信）的能力域返回前瞻提示。"""
    p = xlzsz.prediction_for_skill("cap_03")  # 模型微调，快照中 up conf0.9
    assert p is not None
    assert p["direction"] == "up"
    assert p["confidence"] >= 0.5
    assert "预测上升" in p["note"]


def test_prediction_for_skill_emerging():
    """新涌现方向（近期信号从无到有）返回涌现提示。"""
    p = xlzsz.prediction_for_skill("cap_02")  # Prompt 工程，快照中新涌现
    assert p is not None
    assert p["emerging"] is True
    assert "新涌现" in p["note"]


def test_prediction_for_skill_flat_no_note():
    """平稳/低置信能力域不带前瞻提示（避免噪声），但返回数据。"""
    p = xlzsz.prediction_for_skill("cap_04")  # AI Agent，快照中 flat conf0.4
    assert p is not None
    assert p["note"] == ""


def test_learning_path_attaches_trend(published):
    """学习路径每个缺口携带预测信号；预测上升的能力域学段含前瞻文案。"""
    from datetime import date

    p = _profile([EffectiveSkill(mention="Python", skill_id="cap_07", proficiency="高级")])
    report = engine.match(p, "test-v1")
    path = engine.learning_path(report, as_of=date(2026, 8, 31))
    # 至少一个缺口的学段携带前瞻提示（快照有 up/emerging 能力域）
    notes = [s.learn for s in path.steps if "前瞻" in s.learn]
    assert notes, "预测上升/新涌现的能力域学段应有前瞻提示"
    # 携带前瞻提示的 step 必有结构化 trend 且 note 非空
    for s in path.steps:
        if "前瞻" in s.learn:
            assert s.trend and s.trend["note"]
