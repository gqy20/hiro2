"""候选人文档解析与画像构建（薄适配器：PyMuPDF / python-docx）。"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field


class ResumeRawExtraction(BaseModel):
    """对应 prompts/resume-parse.yml 的 output_schema。"""

    model_config = ConfigDict(extra="forbid")

    skills: list[dict] = Field(default_factory=list, max_length=40)
    experience_years: float | None = None
    education: str = ""
    projects: list[dict] = Field(default_factory=list, max_length=8)


class DocumentParser(Protocol):
    def parse(self, path: Path) -> str: ...


class PdfParser:
    """PyMuPDF 文本抽取。已知局限：双栏版式阅读顺序可能错乱（升级项 MinerU）。"""

    def parse(self, path: Path) -> str:
        import fitz

        doc = fitz.open(path)
        try:
            return "\n".join(page.get_text("text") for page in doc)
        finally:
            doc.close()


class DocxParser:
    """python-docx：段落 + 表格（DOCX 为流式逻辑格式，天然保序）。"""

    def parse(self, path: Path) -> str:
        from docx import Document

        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs if p.text.strip()]
        for table in doc.tables:
            for row in table.rows:
                cells = [c.text.strip() for c in row.cells if c.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts)


def parse_document(path: Path) -> str:
    """按扩展名分发到对应解析器（薄适配器，AGENTS 规则）。"""
    if path.suffix.lower() == ".pdf":
        return PdfParser().parse(path)
    if path.suffix.lower() == ".docx":
        return DocxParser().parse(path)
    if path.suffix.lower() in (".txt", ".md"):
        return path.read_text(encoding="utf-8")
    raise ValueError(f"不支持的格式: {path.suffix}（.doc 老格式请转存 .docx）")


def build_profile(
    candidate_id: str,
    raw: ResumeRawExtraction,
    resolver,
    corrections: list[dict] | None = None,
) -> CandidateProfile:
    """raw extraction + 用户修正 -> effective profile（原始永不覆盖，可审计）。"""
    from .models import CandidateProfile, EffectiveSkill, ProjectEntry

    skills: list[EffectiveSkill] = []
    seen: set[str] = set()
    for s in raw.skills:
        m = s.get("mention", "")
        if not m or m in seen:
            continue
        seen.add(m)
        hit = resolver.resolve(m)
        skills.append(
            EffectiveSkill(
                mention=m,
                skill_id=hit.skill_id,
                point_id=hit.point_id,
                proficiency=s.get("proficiency", "初级"),
                years=s.get("years"),
                source="raw",
            )
        )
    for c in corrections or []:
        m = c.get("mention", "")
        if not m:
            continue
        hit = resolver.resolve(m)
        skills.append(
            EffectiveSkill(
                mention=m,
                skill_id=hit.skill_id,
                point_id=hit.point_id,
                proficiency=c.get("proficiency", "初级"),
                years=c.get("years"),
                source="correction",
            )
        )
    return CandidateProfile(
        candidate_id=candidate_id,
        raw_extraction_id=f"{candidate_id}:raw",
        skills=skills,
        experience_years=raw.experience_years,
        education=raw.education,
        projects=[ProjectEntry.model_validate(p) for p in raw.projects],
        correction_log=corrections or [],
    )


from .models import CandidateProfile  # noqa: E402,F401  (re-export for callers)
