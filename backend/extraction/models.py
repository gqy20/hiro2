"""Extraction 域 DTO：JD 解析的输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class JDParsed(BaseModel):
    """单条 JD 的结构化抽取结果，对应 prompts/jd-skill.yml 的 output_schema。"""

    model_config = ConfigDict(extra="forbid")

    is_ai_role: bool = True
    domain_reason: str = Field(default="", max_length=30)
    responsibilities: list[str] = Field(default_factory=list, max_length=8)
    requirements: list[str] = Field(default_factory=list, max_length=10)
    skill_mentions: list[str] = Field(default_factory=list, max_length=20)
