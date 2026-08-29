"""简历生成域单测：结构渲染、覆盖差建议与结构检查（不依赖 pandoc/PyMuPDF）。"""

from backend.candidates.resume_build import (
    Experience,
    ResumeDraft,
    build_advice,
    draft_to_markdown,
)

JOB = "ai-agent-v2"  # 仓库内已发布版本（必备含 cap_04/cap_01 等）


def _draft(**kw) -> ResumeDraft:
    base = dict(
        name="张三",
        title="AI 应用工程师",
        summary="3 年 LLM 应用开发",
        skills=["Python", "LangChain"],
        experiences=[
            Experience(
                company="某公司", role="后端", period="2022-2024", bullets=["做 RAG 问答 10w 日活"]
            )
        ],
    )
    base.update(kw)
    return ResumeDraft(**base)


def test_markdown_structure() -> None:
    md = draft_to_markdown(_draft())
    assert "# 张三" in md and "## 个人概述" in md and "## 工作经历" in md
    assert "求职意向：AI 应用工程师" in md


def test_advice_flags_missing_required() -> None:
    """Python+LangChain 之外的目标必备技能应逐条给出覆盖差建议。"""
    result = build_advice(_draft(), JOB)
    kinds = {a["kind"] for a in result["advice"]}
    assert "coverage" in kinds
    cov = [a for a in result["advice"] if a["kind"] == "coverage"]
    # ai-agent-v2 必备含 cap_04/cap_01/cap_07/cap_06 等，简历只命中 Python/Agent 域
    assert all(a["severity"] in ("high", "medium") for a in cov)
    assert result["required_covered"] >= 1 and result["required_total"] >= 4


def test_advice_structure_rules_deterministic() -> None:
    """无概述、经历单条、无数字 -> 三类结构建议（确定性）。"""
    result = build_advice(
        ResumeDraft(
            name="李四",
            skills=["Python"],
            experiences=[Experience(company="X", bullets=["负责开发"])],
        ),
        JOB,
    )
    titles = [a["title"] for a in result["advice"] if a["kind"] == "structure"]
    assert "缺少个人概述" in titles
    assert any("描述过少" in t for t in titles)
    # 复跑确定性
    again = build_advice(
        ResumeDraft(
            name="李四",
            skills=["Python"],
            experiences=[Experience(company="X", bullets=["负责开发"])],
        ),
        JOB,
    )
    assert [a["title"] for a in again["advice"]] == [a["title"] for a in result["advice"]]
