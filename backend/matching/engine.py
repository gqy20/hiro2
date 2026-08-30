"""Matching 域：确定性匹配引擎 v1 与学习路径生成。

匹配只接受 CandidateProfile + PublishedJobVersion（contracts 规则），
分数与判定全部确定性可复现；LLM 不参与打分。
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from ..candidates.models import (
    CandidateProfile,
    GapItem,
    LearningPath,
    LearnStep,
    MatchReport,
    Priority,
    Verdict,
)
from . import xlzsz

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED_DIR = ROOT / "data" / "processed" / "jobversions" / "published"
ALGORITHM_VERSION = "match-v1"


def _award_level(contest: dict, award: str) -> str:
    """竞赛获奖 -> 岗位等级（CONTESTS.yml award_to_level）；无获奖返空。"""
    if not award:
        return ""
    return xlzsz.award_to_level(contest.get("scale", ""), award)


def load_published(job_version_id: str) -> dict:
    path = PUBLISHED_DIR / f"{job_version_id}.json"
    if not path.is_file():
        raise FileNotFoundError(f"已发布岗位版本不存在: {job_version_id}")
    return json.loads(path.read_text(encoding="utf-8"))


def _skill_weight(skill: dict) -> float:
    return float(skill.get("weight") or 0)


def match(candidate: CandidateProfile, job_version_id: str) -> MatchReport:
    """确定性匹配：必备/加分域覆盖 + 点级核对，差距按必备优先排序。"""
    job = load_published(job_version_id)
    required = job.get("required_skill_ids") or []
    preferred = job.get("preferred_skill_ids") or []
    have = {s.skill_id for s in candidate.skills if s.skill_id}
    have_points = {s.point_id for s in candidate.skills if s.point_id}
    # 证书/竞赛证据：简历证书名经 CERTS.yml 映射反查能力域（确定性，零 LLM）
    cert_hits: list[dict] = []
    for cert in candidate.certificates:
        cert_hits.extend(xlzsz.match_cert_mention(cert.name))
    # 竞赛证据：项目名命中 CONTESTS.yml + 携带获奖等级（award_to_level 换算）
    contest_hits: list[dict] = []
    for proj in candidate.projects:
        for c in xlzsz.match_contest_mention(proj.name or ""):
            award = getattr(proj, "award", "") or ""
            contest_hits.append({**c, "award": award, "award_level": _award_level(c, award)})

    def judge(skill: dict, is_required: bool) -> GapItem:
        """四档判定（确定性）：达标具备 / 初级部分 / 点级部分 / 缺失。

        证书证据优先：简历 certificates 命中 CERTS.yml 映射（覆盖该能力域）
        时直接判"已具备"，证据 = 证书名（可回链颁发机构）。竞赛经历同理。
        """
        sid = skill["skill_id"]
        domain_points = [p for p in have_points if p.split(".")[0] == sid]
        cand_ev = ""
        verdict: Verdict
        cert_hit = next((c for c in cert_hits if sid in c.get("capability_ids", [])), None)
        if cert_hit:
            verdict = "已具备"
            cand_ev = f"持权威证书：{cert_hit['name']}（{cert_hit.get('issuer', '')}）"
        elif sid in have:
            ev = next(s for s in candidate.skills if s.skill_id == sid)
            cand_ev = f"简历技能：{ev.mention}"
            if ev.years:
                cand_ev += f"（{ev.years} 年，{ev.proficiency}）"
            if ev.years and ev.years >= 2 or ev.proficiency in ("中级", "高级"):
                verdict = "已具备"
            else:
                verdict = "部分具备"
                cand_ev = f"{cand_ev}——初级水平，未达岗位要求深度"
        elif domain_points:
            verdict = "部分具备"
            cand_ev = f"仅有技能点级证据：{', '.join(domain_points[:3])}，能力域整体未覆盖"
        else:
            contest_hit = next(
                (c for c in contest_hits if sid in c.get("capability_ids", [])), None
            )
            if contest_hit:
                award = contest_hit.get("award", "")
                lvl = contest_hit.get("award_level", "")
                if award and lvl:
                    verdict = "部分具备"
                    cand_ev = (
                        f"竞赛获奖证据：{contest_hit['name']} {award}"
                        f"（换算 {lvl}），但未见持续工作/技能深度证据"
                    )
                else:
                    verdict = "部分具备"
                    cand_ev = f"有相关竞赛经历（{contest_hit['name']}），但未见技能/证书直接证据"
            else:
                verdict = "缺失"
                cand_ev = "简历中无该能力域任何证据"
        return GapItem(
            skill_id=sid,
            name=skill.get("name", sid),
            verdict=verdict,
            is_required=is_required,
            job_evidence_ids=[job.get("baseline_evidence_id", "")] if is_required else [],
            candidate_evidence=cand_ev,
        )

    gaps = [judge(s, True) for s in required] + [judge(s, False) for s in preferred]
    req_ok = sum(1 for g in gaps if g.is_required and g.verdict == "已具备")
    req_total = max(len(required), 1)
    pref_ok = sum(1 for g in gaps if not g.is_required and g.verdict == "已具备")
    pref_total = max(len(preferred), 1)
    required_coverage = req_ok / req_total
    preferred_coverage = pref_ok / pref_total
    overall = round(0.7 * required_coverage + 0.3 * preferred_coverage, 3)

    # 关键短板：必备缺失优先，部分具备次之；加分项不掩盖必备缺失（product 验收条款）
    shortboards = [g.name for g in gaps if g.is_required and g.verdict == "缺失"] + [
        g.name for g in gaps if g.is_required and g.verdict == "部分具备"
    ]

    return MatchReport(
        match_id=f"match-{candidate.candidate_id}-{job_version_id}",
        candidate_id=candidate.candidate_id,
        job_version_id=job_version_id,
        algorithm_version=ALGORITHM_VERSION,
        overall_score=overall,
        required_coverage=round(required_coverage, 3),
        preferred_coverage=round(preferred_coverage, 3),
        dimensions=[
            {"name": "必备能力覆盖", "value": round(required_coverage, 3)},
            {"name": "加分能力覆盖", "value": round(preferred_coverage, 3)},
        ],
        gaps=gaps,
        key_shortboards=shortboards,
        evidence_ids=[g.job_evidence_ids[0] for g in gaps if g.job_evidence_ids][:3],
    )


def learning_path(report: MatchReport, as_of: date | None = None) -> LearningPath:
    """学练赛证路径：必备缺失 P0 > 部分具备 P1 > 加分缺失 P2。

    学/练段确定性模板；赛/证段引用真实实体：
    - 证段：CERTS.yml 证书按 capability_ids 反查；
    - 赛段：优先推 race-catalog 中"正在报名/即将截止"的赛事（时间维度，带截止日），
      无则回退 CONTESTS.yml 常设精选赛事，再无则模板文案。
    as_of 为赛事时间窗口的基准日，缺省为今天；测试可注入固定日期保证确定性。
    """
    steps = []
    today = as_of or date.today()
    order = {"缺失": 0, "部分具备": 1, "已具备": 2}
    for g in sorted(
        report.gaps, key=lambda g: (0 if g.is_required else 1, order.get(g.verdict, 3))
    ):
        if g.verdict == "已具备":
            continue
        pri: Priority
        if g.is_required and g.verdict == "缺失":
            pri, reason = "P0 必备补齐", "岗位必备能力缺失，优先补齐"
        elif g.is_required:
            pri, reason = "P1 巩固提升", "已有相邻基础，向目标技能点深化"
        else:
            pri, reason = "P2 加分拓展", "非必备，作为差异化加分项拓展"

        # 赛/证段：真实实体优先，无匹配时回退模板；同时保留结构化对象供前端渲染可点击卡片。
        certs = xlzsz.certs_for_skill(g.skill_id, limit=2)
        open_contests = xlzsz.open_contests_for_skill(g.skill_id, today, limit=2)
        curated_contests = xlzsz.contests_for_skill(g.skill_id, limit=2)
        cert_cards = [
            {"name": c["name"], "issuer": c.get("issuer", ""), "url": c.get("url", "")}
            for c in certs
        ]
        # 赛事卡片：正在报名的赛事（带截止日）优先，再补常设精选赛事作参考。
        contest_cards = [
            {
                "name": c["name"],
                "organizer": c.get("organizer", ""),
                "url": c.get("url", ""),
                "status": c["status"],
                "register_end": c["register_end"],
                "days_left": c["days_left"],
            }
            for c in open_contests
        ]
        if len(contest_cards) < 3:
            contest_cards += [
                {
                    "name": c["name"],
                    "organizer": c.get("organizer", ""),
                    "url": c.get("url", ""),
                    "status": "常设",
                    "register_end": "",
                    "days_left": None,
                }
                for c in curated_contests
            ][: 3 - len(contest_cards)]
        if certs:
            cert_names = "、".join(f"{c['name']}（{c['issuer']}）" for c in certs)
            certify = f"考取或对照权威认证：{cert_names}；并整理项目证据形成能力证明材料"
        else:
            certify = f"整理项目证据形成 {g.name} 能力证明材料"
        if open_contests:
            race_desc = "、".join(
                f"{c['name']}（截止 {c['register_end']}，剩 {c['days_left']} 天）"
                for c in open_contests
            )
            evaluate = f"正在报名的赛事，以赛促学：{race_desc}"
        elif curated_contests:
            race_names = "、".join(c["name"] for c in curated_contests)
            evaluate = f"参加实践评测或赛事检验：{race_names}"
        else:
            evaluate = f"在项目复盘中自评 {g.name} 的独立完成度"
        # 学段三层回退：国家职业标准官方知识点 -> 能力域自身技能点 -> 泛泛模板。
        know = xlzsz.knowledge_for_skill(g.skill_id, limit=2)
        if know:
            std = know[0]["std_name"]
            points = "；".join(k["knowledge"] for k in know)
            learn = f"对照《{std}》国家职业标准学习：{points}"
        else:
            skill_points = xlzsz.skill_points_for_skill(g.skill_id, limit=4)
            if skill_points:
                learn = f"学习 {g.name} 的核心技能点：{'、'.join(skill_points)}"
            else:
                learn = f"学习 {g.name} 领域核心知识点与主流方法"
        # 预测信号（时间情报域 -> 学练段）：只存结构化 trend（由诊断实时读取快照），
        # 不拼进学段文案——避免匹配时固化的前瞻过时，与实时徽标矛盾。
        trend = xlzsz.prediction_for_skill(g.skill_id)

        steps.append(
            LearnStep(
                skill_id=g.skill_id,
                name=g.name,
                priority=pri,
                reason=reason,
                learn=learn,
                practice=f"完成一个包含 {g.name} 的实战小项目并沉淀到简历",
                evaluate=evaluate,
                certify=certify,
                certificates=cert_cards,
                contests=contest_cards,
                trend=trend,
            )
        )
    return LearningPath(
        candidate_id=report.candidate_id,
        job_version_id=report.job_version_id,
        match_id=report.match_id,
        steps=steps,
        generated_by=f"{ALGORITHM_VERSION} 实体映射规则",
    )
