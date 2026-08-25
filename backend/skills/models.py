"""Skills 域 DTO：离线词典生产的候选输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SkillAliasCandidate(BaseModel):
    """单个未归一词的归派候选。LLM 只出候选，人审后才进入词典。"""

    model_config = ConfigDict(extra="forbid")

    word: str = Field(min_length=1, max_length=60)
    is_skill: bool
    capability_id: str | None = Field(default=None, pattern=r"^cap_\d{2}$")
    point_name: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(default="", max_length=200)


class SkillAliasCandidateList(BaseModel):
    """批量归派的输出包装，对应 prompts/skill-alias.yml 的 output_schema。"""

    model_config = ConfigDict(extra="forbid")

    candidates: list[SkillAliasCandidate] = Field(default_factory=list, max_length=50)


class PositionSkill(BaseModel):
    """单个岗位职责简介的结构化抽取结果。"""

    model_config = ConfigDict(extra="forbid")

    position_id: str = Field(min_length=3, max_length=10)
    responsibilities: list[str] = Field(default_factory=list, max_length=8)
    requirements: list[str] = Field(default_factory=list, max_length=8)
    skill_mentions: list[str] = Field(default_factory=list, max_length=15)


class PositionSkillList(BaseModel):
    """对应 prompts/position-skill.yml 的 output_schema（单岗位单次调用）。"""

    model_config = ConfigDict(extra="forbid")

    position: PositionSkill
