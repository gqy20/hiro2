"""Temporal 域 DTO：日报事件抽取的 Pydantic 模型（唯一运行时 Schema 来源）。"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal[
    "research",
    "standard_release",
    "model_release",
    "open_source",
    "productization",
    "adoption",
    "policy",
    "rumor",
]

FactGrade = Literal["fact", "report", "opinion"]


class ReportEvent(BaseModel):
    """一篇早报内的一条独立新闻事件。多余字段视为校验失败，不静默接受。"""

    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    title: str = Field(min_length=2, max_length=120)
    summary: str = Field(min_length=5, max_length=500)
    entities: list[str] = Field(default_factory=list, max_length=10)
    fact_grade: FactGrade
    urls: list[str] = Field(default_factory=list, max_length=5)
    skill_mentions: list[str] = Field(default_factory=list, max_length=10)


class ReportEventList(BaseModel):
    """单篇早报的事件抽取输出，对应 prompts/report-event.yml 的 output_schema。"""

    model_config = ConfigDict(extra="forbid")

    events: list[ReportEvent] = Field(default_factory=list, max_length=30)


class ExtractedEvent(ReportEvent):
    """落盘形态：在模型输出之上附加溯源字段。溯源字段由确定性代码填充，不经 LLM。"""

    event_id: str
    item_id: str
    published_at: str | None
    prompt_version: int
    model_version: str
