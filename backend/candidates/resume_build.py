"""简历生成域（V1）：ResumeDraft 结构化草稿 -> Markdown/PDF 渲染 + 确定性建议。

渲染复用 md2res 同链路（pandoc -> HTML -> PyMuPDF Story，A4 单栏）；
建议为确定性层（零 LLM）：技能归一 -> 目标岗位版本覆盖差 -> 技能点具体化
-> 结构检查（V1 只归一显式技能字段，正文 bullet 不做抽取，边界诚实标注）。
"""

from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path

from pydantic import BaseModel, Field

from ..matching.engine import load_published
from ..skills.resolver import load_resolver

# ---------------------------------------------------------------------------
# DTO


class Experience(BaseModel):
    company: str = ""
    role: str = ""
    period: str = ""
    bullets: list[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str = ""
    desc: str = ""
    bullets: list[str] = Field(default_factory=list)


class Education(BaseModel):
    school: str = ""
    major: str = ""
    degree: str = ""
    period: str = ""


class ResumeDraft(BaseModel):
    name: str = ""
    contact: str = ""  # 单行联系方式（电话/邮箱/城市），渲染原样输出
    title: str = ""  # 求职意向标题（如"AI 应用工程师"）
    summary: str = ""
    skills: list[str] = Field(default_factory=list)
    experiences: list[Experience] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)


class AdviceItem(BaseModel):
    kind: str  # coverage | specificity | structure
    severity: str  # high | medium | low
    title: str
    detail: str
    suggestion: str
    skill_id: str | None = None
    evidence: dict[str, str] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 渲染


def draft_to_markdown(draft: ResumeDraft) -> str:
    """草稿 -> 简历 Markdown（结构固定，无个人信息写入日志）。"""
    lines: list[str] = []
    if draft.name:
        lines.append(f"# {draft.name}")
    if draft.title:
        lines.append(f"**求职意向：{draft.title}**")
    if draft.contact:
        lines.append(draft.contact)
    if draft.summary:
        lines += ["", "## 个人概述", "", draft.summary]
    if draft.skills:
        lines += ["", "## 专业技能", "", "、".join(draft.skills)]
    if draft.experiences:
        lines += ["", "## 工作经历"]
        for e in draft.experiences:
            head = " ｜ ".join(x for x in (e.company, e.role, e.period) if x)
            if head:
                lines += ["", f"**{head}**"]
            lines += [f"- {b}" for b in e.bullets if b.strip()]
    if draft.projects:
        lines += ["", "## 项目经历"]
        for p in draft.projects:
            head = p.name + (f"（{p.desc}）" if p.desc else "")
            if head.strip("（）"):
                lines += ["", f"**{head}**"]
            lines += [f"- {b}" for b in p.bullets if b.strip()]
    if draft.education:
        lines += ["", "## 教育背景"]
        for ed in draft.education:
            head = " ｜ ".join(x for x in (ed.school, ed.major, ed.degree, ed.period) if x)
            if head:
                lines += ["", f"**{head}**"]
    return "\n".join(lines) + "\n"


def _pandoc_html(md_text: str) -> str:
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(md_text)
        path = f.name
    try:
        r = subprocess.run(
            ["pandoc", path, "-t", "html", "--wrap=none"],
            capture_output=True,
            text=True,
            check=True,
        )
        return r.stdout
    finally:
        Path(path).unlink(missing_ok=True)


def render_pdf(draft: ResumeDraft, out_path: Path) -> Path:
    """草稿 -> A4 单栏 PDF（pandoc + PyMuPDF Story，与 md2res 测试集同链路）。"""
    import pymupdf

    html = _pandoc_html(draft_to_markdown(draft))
    story = pymupdf.Story(html=html)  # type: ignore[attr-defined]
    media = pymupdf.Rect(0, 0, 595, 842)
    with pymupdf.DocumentWriter(str(out_path)) as writer:  # type: ignore[attr-defined]
        more = 1
        while more:
            dev = writer.begin_page(media)
            more, _ = story.place(pymupdf.Rect(54, 54, 541, 788))
            story.draw(dev)
            writer.end_page()
    return out_path


# ---------------------------------------------------------------------------
# 确定性建议


_NUM = re.compile(r"\d")


def build_advice(draft: ResumeDraft, job_version_id: str) -> dict:
    """确定性建议（零 LLM）：覆盖差 / 技能点具体化 / 结构检查，每条带证据。"""
    job = load_published(job_version_id)
    job_name = job.get("title") or job_version_id
    jd_count = (job.get("evidence") or {}).get("jd_count") or 0
    resolver = load_resolver()

    mentioned_ids: set[str] = set()
    norm_map: dict[str, str] = {}
    for word in draft.skills:
        hit = resolver.resolve(word)
        if hit.skill_id:
            mentioned_ids.add(hit.skill_id)
            norm_map[word] = hit.skill_id

    advice: list[AdviceItem] = []

    # 1) 覆盖差：目标岗位必备/加分技能在简历中未体现
    for field, label in (("required_skill_ids", "必备"), ("preferred_skill_ids", "加分")):
        for skill in job.get(field) or []:
            sid = skill["skill_id"]
            if sid in mentioned_ids:
                continue
            advice.append(
                AdviceItem(
                    kind="coverage",
                    severity="high" if label == "必备" else "medium",
                    title=f"未体现目标岗位{label}技能：{skill.get('name', sid)}",
                    detail=(
                        f"目标岗位《{job_name}》的{label}技能 {skill.get('name', sid)}"
                        f"（市场权重 {skill.get('weight', 0):.1%}）在你的技能区未出现"
                    ),
                    suggestion="有相关经验时，在技能区或经历中补充该能力的具体表述",
                    skill_id=sid,
                    evidence={
                        "job_version_id": job_version_id,
                        "weight": f"{skill.get('weight', 0):.1%}",
                        "jd_count": str(jd_count),
                    },
                )
            )

    # 2) 具体化：已具备的域给出技能点细化方向（SKILLS.yml points 反查）
    points_by_cap: dict[str, list[str]] = {}
    for ent in resolver.entries:
        names = [name for name, _aliases in ent.points]
        if names:
            points_by_cap.setdefault(ent.capability_id, [])
            for name in names:
                if name not in points_by_cap[ent.capability_id]:
                    points_by_cap[ent.capability_id].append(name)
    for word, sid in norm_map.items():
        pts = points_by_cap.get(sid) or []
        if pts:
            advice.append(
                AdviceItem(
                    kind="specificity",
                    severity="low",
                    title=f"「{word}」可以更具体",
                    detail=f"该能力域在岗位画像中包含技能点：{'、'.join(pts[:5])}",
                    suggestion="bullet 写出具体环节（选型/评测/调优），比罗列名词更有说服力",
                    skill_id=sid,
                    evidence={"job_version_id": job_version_id, "points": "、".join(pts[:5])},
                )
            )

    # 3) 结构检查：概述缺省 / 经历 bullet 过少 / 无量化数字
    if not draft.summary.strip():
        advice.append(
            AdviceItem(
                kind="structure",
                severity="medium",
                title="缺少个人概述",
                detail="招聘方第一屏看不到你的定位",
                suggestion="补 2~3 句：方向 + 年限 + 最相关的一项成果",
            )
        )
    thin = [
        f"{e.company or e.role or '某段经历'}（仅 {len(e.bullets)} 条）"
        for e in draft.experiences
        if len([b for b in e.bullets if b.strip()]) < 2
    ]
    if thin:
        advice.append(
            AdviceItem(
                kind="structure",
                severity="low",
                title="部分经历描述过少",
                detail="；".join(thin),
                suggestion="每段经历建议 2~4 条 bullet，覆盖职责、动作与结果",
            )
        )
    bullets = [b for e in draft.experiences for b in e.bullets] + [
        b for p in draft.projects for b in p.bullets
    ]
    if bullets and not any(_NUM.search(b) for b in bullets):
        advice.append(
            AdviceItem(
                kind="structure",
                severity="low",
                title="经历中没有任何数字",
                detail="量化结果（规模/百分比/时长）是简历可信度的主要来源",
                suggestion="至少把 1~2 条 bullet 改写为带量化结果的表述",
            )
        )

    required_ids = [s["skill_id"] for s in job.get("required_skill_ids") or []]
    covered = sum(1 for sid in required_ids if sid in mentioned_ids)
    return {
        "job_version_id": job_version_id,
        "job_title": job_name,
        "required_total": len(required_ids),
        "required_covered": covered,
        "advice": [a.model_dump() for a in advice],
        "note": "V1 确定性层：仅归一显式技能字段，正文 bullet 不做抽取；LLM 表述建议为 V2",
    }
