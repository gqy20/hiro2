"""Jobs 域 DTO：岗位目录映射的输出模型。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RoleMatch(BaseModel):
    """单条 JD 到标准岗位的映射候选，对应 prompts/role-map.yml 的 output_schema。"""

    model_config = ConfigDict(extra="forbid")

    jd_id: str = Field(min_length=3, max_length=60)
    is_match: bool
    position_id: str | None = Field(default=None, pattern=r"^pos_\d{2}$")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(default="", max_length=40)
