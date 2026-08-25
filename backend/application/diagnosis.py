"""Diagnosis Use Case：候选人画像 + 匹配报告 + 学习路径的聚合 View Model。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .repos import P


class _VM(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SkillMatchVM(_VM):
    name: str
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


class JobVM(_VM):
    title: str
    version: str
    window: str
    evidenceCount: int


class GapVM(_VM):
    skill: str
    reason: str
    priority: Literal["high", "medium"]
    action: str


class DiagnosisVM(_VM):
    fixtureVersion: str
    mode: str = "real"
    candidate: CandidateVM
    job: JobVM
    report: dict


def _load(p: Path) -> dict:
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def build_diagnosis(candidate_id: str, job_version_id: str = "ai-agent-v2") -> DiagnosisVM:
    """从 processed 产物聚合 diagnosis 视图（确定性组装，无 LLM）。"""
    cand = _load(P / "candidates" / f"{candidate_id}.json")
    report = _load(P / "candidates" / "matches" / f"{candidate_id}-{job_version_id}-report.json")
    path = _load(P / "candidates" / "matches" / f"{candidate_id}-{job_version_id}-path.json")
    job = _load(P / "jobversions" / "published" / f"{job_version_id}.json")
    if not cand or not report:
        raise FileNotFoundError(f"候选人或匹配报告不存在: {candidate_id}")

    skills = [
        SkillMatchVM(
            name=s["mention"],
            level=s.get("proficiency", ""),
            years=s.get("years"),
            status="ready" if s.get("skill_id") else "missing",
            evidence=f"来源: {s.get('resolved_by', 'dict')}",
        )
        for s in cand.get("skills", [])
    ]
    gaps = [
        GapVM(
            skill=g["name"],
            reason=g.get("candidate_evidence", ""),
            priority="high" if g.get("is_required") else "medium",
            action=next(
                (st["learn"] for st in path.get("steps", []) if st["skill_id"] == g["skill_id"]),
                "",
            ),
        )
        for g in report.get("gaps", [])
        if g.get("verdict") != "已具备"
    ]
    return DiagnosisVM(
        fixtureVersion="v2",
        candidate=CandidateVM(
            id=cand["candidate_id"],
            name=cand.get("candidate_id", ""),
            headline=f"{cand.get('education', '')} | {cand.get('experience_years', '')} 年",
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
            evidenceCount=job.get("evidence", {}).get("jd_count", 0),
        ),
        report={
            "matchId": report.get("match_id", ""),
            "algorithmVersion": report.get("algorithm_version", ""),
            "overallScore": report.get("overall_score", 0),
            "gaps": [g.model_dump() for g in gaps],
        },
    )


def list_candidates() -> list[dict]:
    """列出已有画像的候选人（供页面选择）。"""
    out = []
    for f in sorted((P / "candidates").glob("*.json")):
        d = _load(f)
        if d:
            out.append(
                {
                    "id": d["candidate_id"],
                    "education": d.get("education", ""),
                    "experienceYears": d.get("experience_years"),
                    "skills": len(d.get("skills", [])),
                }
            )
    return out
