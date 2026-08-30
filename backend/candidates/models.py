"""Candidates 域 DTO：候选人画像与匹配报告（contracts.md 语义）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Proficiency = Literal["初级", "中级", "高级"]
Verdict = Literal["缺失", "部分具备", "已具备"]
Priority = Literal["P0 必备补齐", "P1 巩固提升", "P2 加分拓展"]


class EffectiveSkill(BaseModel):
    """归一后的有效技能：原词 + canonical 能力/技能点 + 熟练度 + 来源。"""

    model_config = ConfigDict(extra="forbid")

    mention: str
    skill_id: str | None = None
    point_id: str | None = None
    proficiency: Proficiency = "初级"
    years: float | None = None
    source: Literal["raw", "correction"] = "raw"
    resolved_by: Literal["dict", "llm", "unmatched"] = "dict"
    reason: str = ""


class ProjectEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str = ""
    skill_mentions: list[str] = Field(default_factory=list, max_length=15)
    award: str = ""  # 竞赛获奖等级（如"国家级一等奖""省级二等奖"），无则空


class WorkExperience(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company: str = ""
    title: str
    start_date: str = ""
    end_date: str = ""
    summary: str = ""
    achievements: list[str] = Field(default_factory=list, max_length=5)
    skill_mentions: list[str] = Field(default_factory=list, max_length=15)

    @model_validator(mode="before")
    @classmethod
    def normalize_nulls(cls, obj):
        if isinstance(obj, dict):
            obj = {key: ("" if value is None else value) for key, value in obj.items()}
        return obj


class EducationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    school: str
    major: str = ""
    degree: str = ""
    start_date: str = ""
    end_date: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_nulls(cls, obj):
        if isinstance(obj, dict):
            obj = {key: ("" if value is None else value) for key, value in obj.items()}
        return obj


class CertificateEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    issuer: str = ""
    issued_date: str = ""

    @model_validator(mode="before")
    @classmethod
    def normalize_nulls(cls, obj):
        if isinstance(obj, dict):
            obj = {key: ("" if value is None else value) for key, value in obj.items()}
        return obj


class CandidateProfile(BaseModel):
    """effective_profile = raw_extraction + user_corrections（原始抽取永不覆盖）。"""

    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    raw_extraction_id: str
    name: str = ""
    skills: list[EffectiveSkill] = Field(default_factory=list, max_length=60)
    experience_years: float | None = None
    education: str = ""
    location: str = ""
    work_experiences: list[WorkExperience] = Field(default_factory=list, max_length=10)
    education_history: list[EducationEntry] = Field(default_factory=list, max_length=8)
    certificates: list[CertificateEntry] = Field(default_factory=list, max_length=12)
    portfolio_urls: list[str] = Field(default_factory=list, max_length=8)
    languages: list[str] = Field(default_factory=list, max_length=8)
    projects: list[ProjectEntry] = Field(default_factory=list, max_length=10)
    correction_log: list[dict] = Field(default_factory=list)


class GapItem(BaseModel):
    """差距项：判定 + 双向证据（岗位凭什么要求 / 凭什么判你不具备）。"""

    model_config = ConfigDict(extra="forbid")

    skill_id: str
    name: str
    verdict: Verdict
    is_required: bool
    job_evidence_ids: list[str] = Field(default_factory=list, max_length=5)
    candidate_evidence: str = ""


class MatchReport(BaseModel):
    """匹配报告：确定性引擎输出，算法版本可追溯。"""

    model_config = ConfigDict(extra="forbid")

    match_id: str
    candidate_id: str
    job_version_id: str
    algorithm_version: str
    overall_score: float
    required_coverage: float
    preferred_coverage: float
    dimensions: list[dict]
    gaps: list[GapItem]
    key_shortboards: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    status: Literal["DRAFT", "FINAL"] = "FINAL"


class LearnStep(BaseModel):
    """学练赛证路径中的一步。"""

    model_config = ConfigDict(extra="forbid")

    skill_id: str
    name: str
    priority: Priority
    reason: str
    learn: str
    practice: str
    evaluate: str
    certify: str
    # 结构化实体（供前端渲染可点击卡片）：证书 {name, issuer, url}、竞赛 {name, organizer, url}
    certificates: list[dict] = Field(default_factory=list)
    contests: list[dict] = Field(default_factory=list)


class LearningPath(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str
    job_version_id: str
    match_id: str
    steps: list[LearnStep]
    generated_by: str
