"""Diagnosis Use Case：候选人画像 + 匹配报告 + 学习路径的聚合 View Model。"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .repos import P


class _VM(BaseModel):
    model_config = ConfigDict(
        alias_generator=lambda name: (
            name.split("_")[0] + "".join(part.capitalize() for part in name.split("_")[1:])
        ),
        populate_by_name=True,
        extra="forbid",
    )


class SkillMatchVM(_VM):
    name: str
    skill_id: str | None = None
    point_id: str | None = None
    level: str = ""
    years: float | None = None
    status: Literal["ready", "partial", "missing"] = "missing"
    evidence: str = ""


class ProjectVM(_VM):
    id: str
    text: str


class CandidateVM(_VM):
    id: str
    name: str
    headline: str
    location: str = ""
    skills: list[SkillMatchVM]
    projects: list[ProjectVM]
    user_corrections: list[dict] = Field(default_factory=list)


class JobVM(_VM):
    title: str
    version: str
    window: str
    evidence_count: int


class GapVM(_VM):
    skill: str
    reason: str
    priority: Literal["high", "medium"]
    action: str
    practice: str = ""
    evaluate: str = ""
    certify: str = ""


class DiagnosisVM(_VM):
    fixture_version: str
    mode: str = "real"
    candidate: CandidateVM
    job: JobVM
    report: dict
    target_jobs: list[dict] = Field(default_factory=list)


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _load_db_diagnosis(candidate_id: str, job_version_id: str) -> tuple[dict, dict, dict] | None:
    """数据库可用时读取候选人当前画像、最新匹配报告和岗位版本。"""
    dsn = os.getenv("DATABASE_URL")
    if not dsn:
        return None
    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT effective_profile FROM candidates WHERE candidate_id = %s", (candidate_id,)
        )
        candidate = cur.fetchone()
        cur.execute(
            """SELECT match_id, algorithm_version, overall_score, dimensions, gaps, evidence_ids
               FROM match_reports WHERE candidate_id = %s AND job_version_id = %s
               ORDER BY created_at DESC LIMIT 1""",
            (candidate_id, job_version_id),
        )
        report = cur.fetchone()
        cur.execute(
            """SELECT title, valid_from, evidence_ids, required_skills FROM job_versions
               WHERE version_id = %s AND status = 'PUBLISHED'""",
            (job_version_id,),
        )
        job = cur.fetchone()
    if not candidate or not report or not job:
        return None
    return (
        candidate[0],
        {
            "match_id": report[0],
            "algorithm_version": report[1],
            "overall_score": report[2],
            "dimensions": report[3],
            "gaps": report[4],
            "evidence_ids": report[5],
        },
        {
            "title": job[0],
            "valid_from": job[1].isoformat() if job[1] else "",
            "evidence": {"evidence_ids": job[2]},
            # 对齐文件路径的键名，供 requiredTotal 计算复用
            "required_skill_ids": job[3] or [],
        },
    )


def _candidate_display_name(candidate: dict) -> str:
    """返回脱敏展示名，禁止将内部 candidate_id 直接暴露给界面。"""
    if name := str(candidate.get("name", "")).strip():
        return name
    candidate_id = str(candidate.get("candidate_id", ""))
    suffix = re.search(r"(?:^|_)(\d+)$", candidate_id)
    return f"候选人 {suffix.group(1)}" if suffix else "候选人"


def _format_experience(value: object) -> str:
    if not isinstance(value, int | float):
        return ""
    years = f"{value:g}"
    return f"{years} 年经验"


def _format_headline(candidate: dict) -> str:
    education = str(candidate.get("education", "")).strip()
    experience = _format_experience(candidate.get("experience_years"))
    return " · ".join(part for part in (education, experience) if part)


def _skill_evidence(skill: dict) -> str:
    return "人工修正" if skill.get("source") == "correction" else "简历提及"


def _skill_status(skill: dict) -> Literal["ready", "partial", "missing"]:
    if not skill.get("skill_id"):
        return "missing"
    if skill.get("proficiency") == "初级" and (skill.get("years") or 0) < 2:
        return "partial"
    return "ready"


def build_diagnosis(candidate_id: str, job_version_id: str = "ai-agent-v2") -> DiagnosisVM:
    """从 processed 产物聚合 diagnosis 视图（确定性组装，无 LLM）。"""
    database = _load_db_diagnosis(candidate_id, job_version_id)
    cand = database[0] if database else _load(P / "candidates" / f"{candidate_id}.json")
    report = (
        database[1]
        if database
        else _load(P / "candidates" / "matches" / f"{candidate_id}-{job_version_id}-report.json")
    )
    path = _load(P / "candidates" / "matches" / f"{candidate_id}-{job_version_id}-path.json")
    job = (
        database[2]
        if database
        else _load(P / "jobversions" / "published" / f"{job_version_id}.json")
    )
    if not cand or not report:
        raise FileNotFoundError(f"候选人或匹配报告不存在: {candidate_id}")

    skills = [
        SkillMatchVM(
            name=s["mention"],
            skill_id=s.get("skill_id"),
            point_id=s.get("point_id"),
            level=s.get("proficiency", ""),
            years=s.get("years"),
            status=_skill_status(s),
            evidence=_skill_evidence(s),
        )
        for s in cand.get("skills", [])
    ]

    def _step(skill_id: str) -> dict:
        return next(
            (st for st in path.get("steps", []) if st["skill_id"] == skill_id),
            {},
        )

    gaps = [
        GapVM(
            skill=g["name"],
            reason=g.get("candidate_evidence", ""),
            priority="high" if g.get("is_required") else "medium",
            action=_step(g["skill_id"]).get("learn", ""),
            practice=_step(g["skill_id"]).get("practice", ""),
            evaluate=_step(g["skill_id"]).get("evaluate", ""),
            certify=_step(g["skill_id"]).get("certify", ""),
        )
        for g in report.get("gaps", [])
        if g.get("verdict") != "已具备"
    ]
    from .career import load_career_state

    career_state = load_career_state(candidate_id, job_version_id)
    return DiagnosisVM(
        fixture_version="v2",
        candidate=CandidateVM(
            id=cand["candidate_id"],
            name=_candidate_display_name(cand),
            headline=_format_headline(cand),
            skills=skills,
            projects=[
                ProjectVM(id=f"proj-{i}", text=p["name"])
                for i, p in enumerate(cand.get("projects", []))
            ],
        ),
        job=JobVM(
            title=job.get("title", job_version_id),
            version=job_version_id,
            window=job.get("valid_from", ""),
            evidence_count=len(job.get("evidence", {}).get("evidence_ids", [])),
        ),
        report={
            "matchId": report.get("match_id", ""),
            "algorithmVersion": report.get("algorithm_version", ""),
            "overallScore": report.get("overall_score", 0),
            "requiredMet": sum(
                1
                for g in report.get("gaps", [])
                if g.get("is_required") and g.get("verdict") == "已具备"
            ),
            "requiredTotal": len(job.get("required_skill_ids", [])),
            "gaps": [g.model_dump() for g in gaps],
            "career": career_state,
        },
        target_jobs=list_target_jobs(candidate_id),
    )


def list_target_jobs(candidate_id: str) -> list[dict]:
    """只列出该候选人已有匹配报告的已发布岗位，避免无依据目标。"""
    dsn = os.getenv("DATABASE_URL")
    if dsn:
        import psycopg

        with psycopg.connect(dsn) as conn, conn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT mr.job_version_id, jv.title
                   FROM match_reports mr JOIN job_versions jv ON jv.version_id = mr.job_version_id
                   WHERE mr.candidate_id = %s AND jv.status = 'PUBLISHED'
                   ORDER BY jv.title""",
                (candidate_id,),
            )
            return [{"version": row[0], "title": row[1]} for row in cur.fetchall()]
    out = []
    report_dir = P / "candidates" / "matches"
    for report_file in sorted(report_dir.glob(f"{candidate_id}-*-report.json")):
        version = report_file.name.removeprefix(f"{candidate_id}-").removesuffix("-report.json")
        job = _load(P / "jobversions" / "published" / f"{version}.json")
        if job:
            out.append({"version": version, "title": job.get("title", version)})
    return out


def list_candidates() -> list[dict]:
    """列出已有画像的候选人（供页面选择）。"""
    out = []
    for f in sorted((P / "candidates").glob("*.json")):
        d = _load(f)
        if d.get("candidate_id"):
            out.append(
                {
                    "id": d["candidate_id"],
                    "name": _candidate_display_name(d),
                    "education": d.get("education", ""),
                    "experienceYears": d.get("experience_years"),
                    "skills": len(d.get("skills", [])),
                }
            )
    return out
