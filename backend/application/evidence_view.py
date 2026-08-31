"""证据 View Model 与解析（evidence_id -> EvidenceVM）。

service（新岗位/岗位更新）与 diagnosis（匹配依据）共用同一解析逻辑，
摘录联查（事件/ JD）由调用方传入已加载的索引，保持本模块无 IO。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

SourceType = Literal["招聘 JD", "技术日报", "职业标准"]
EvidenceStance = Literal["支持", "反证"]

_SOURCE_TYPE: dict[str, SourceType] = {"jd": "招聘 JD", "ev": "技术日报", "xlsx": "职业标准"}
_DEFAULT_SOURCE_TYPE: SourceType = "技术日报"


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.capitalize() for w in rest)


class _VM(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class EvidenceVM(_VM):
    id: str
    source: str
    source_type: SourceType
    published_at: str | None = None
    collected_at: str | None = None
    quality: float
    excerpt: str
    full_text: str
    source_url: str | None = None
    stance: EvidenceStance = "支持"


def evidence_to_vm(ev: dict, events: dict, jd: dict) -> EvidenceVM:
    """原始证据记录 -> EvidenceVM；events/jd 为已加载的联查索引（可为空）。"""
    prefix = ev["evidence_id"].split(":", 1)[0]
    payload = ev.get("payload") or {}
    span = ev.get("source_span") or {}
    excerpt, full, url = "", "", None
    if prefix == "ev":
        src = events.get(span.get("event_id", ""), {})
        full = src.get("summary") or payload.get("title") or ""
        url = (ev.get("urls") or [None])[0]
    elif prefix == "jd":
        src = jd.get(span.get("jd_id", ""), {})
        full = "；".join((src.get("responsibilities") or []) + (src.get("requirements") or []))
        url = None
    else:
        full = "；".join(payload.get("responsibilities") or [])
    excerpt = (full or payload.get("title") or "")[:160]
    return EvidenceVM(
        id=ev["evidence_id"],
        source=ev.get("source_id", ""),
        source_type=_SOURCE_TYPE.get(prefix, _DEFAULT_SOURCE_TYPE),
        published_at=ev.get("published_at"),
        collected_at=ev.get("collected_at"),
        quality=ev.get("quality_score", 0.6),
        excerpt=excerpt,
        full_text=full or excerpt,
        source_url=url,
    )
