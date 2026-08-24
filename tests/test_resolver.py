"""技能归一化 resolver 测试：词典加载、归一化匹配、时间闸门、未命中路径。"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.skills.resolver import (  # noqa: E402
    EarnedAlias,
    SkillEntry,
    SkillResolver,
    load_resolver,
    normalize,
)


def test_normalize_handles_width_and_case() -> None:
    assert normalize("ＭＣＰ") == "mcp"
    assert normalize("  Fine-Tuning ") == "fine-tuning"
    assert normalize("混合专家（MoE）架构") == normalize("混合专家(moe)架构")


def test_resolver_matches_alias_point_and_name() -> None:
    entries = [
        SkillEntry(
            capability_id="cap_04",
            name="AI Agent",
            aliases=("Agent", "智能体"),
            points=(("MCP", ("Model Context Protocol",)),),
        )
    ]
    r = SkillResolver(entries, version=1)
    assert r.resolve("智能体").matched_by == "alias"
    assert r.resolve("AI Agent").skill_id == "cap_04"
    mcp = r.resolve("MCP")
    assert mcp.point_id == "cap_04.MCP" and mcp.matched_by == "point_name"
    assert r.resolve("Model Context Protocol").point_id == "cap_04.MCP"
    miss = r.resolve("量子计算")
    assert miss.matched_by == "unmatched" and miss.skill_id is None


def test_earned_alias_time_gate() -> None:
    """语料习得别名受 effective_from 时间闸门控制，人工先验不受限。"""
    entries = [SkillEntry(capability_id="cap_04", name="AI Agent", aliases=("智能体",), points=())]
    earned = [
        EarnedAlias(
            mention="MCP工具",
            capability_id="cap_04",
            point_name="MCP",
            effective_from=date(2025, 3, 24),
        )
    ]
    # 站在首见日之前：习得别名不可用
    before = SkillResolver(entries, 1, earned, as_of=date(2025, 3, 23))
    assert before.resolve("MCP工具").matched_by == "unmatched"
    assert before.resolve("智能体").matched_by == "alias"  # 人工先验不受闸门影响
    # 站在首见日当天及之后：可用，且命中类型为 earned
    after = SkillResolver(entries, 1, earned, as_of=date(2025, 3, 24))
    hit = after.resolve("MCP工具")
    assert hit.matched_by == "earned" and hit.point_id == "cap_04.MCP"
    # 不带 as_of（日常统计）：全部可用
    assert SkillResolver(entries, 1, earned).resolve("MCP工具").matched_by == "earned"


def test_official_dictionaries_load_and_gate() -> None:
    r = load_resolver()
    assert r.version >= 1 and len(r.entries) == 30
    gated = load_resolver(as_of=date(2025, 1, 1))
    words = ("文本生成", "工作流", "基准测试")
    assert all(r.resolve(w).skill_id for w in words)  # 全词典下习得词可用
    assert not any(gated.resolve(w).skill_id for w in words)  # 2025-01 视角下被闸掉


def test_official_dictionary_loads_and_matches() -> None:
    r = load_resolver()
    cases = [("MCP", "cap_04"), ("RAG", "cap_06"), ("推理模型", "cap_01"), ("语音合成", "cap_05")]
    for mention, expected in cases:
        assert r.resolve(mention).skill_id == expected, mention
    # 词形变体也应命中
    assert r.resolve("ＭＣＰ").skill_id == "cap_04"


def test_every_entry_maps_to_excel_capability() -> None:
    """词典 capability_id 必须存在于 Excel 30 能力清单中，防止两套体系漂移。"""
    import json

    caps_file = (
        Path(__file__).resolve().parents[1] / "data/processed/capability-matrix/capabilities.json"
    )
    if not caps_file.is_file():
        return  # 原始数据未导入的环境跳过
    caps = json.loads(caps_file.read_text(encoding="utf-8"))["capabilities"]
    valid = {c["capability_id"] for c in caps}
    r = load_resolver()
    assert {e.capability_id for e in r.entries} <= valid


def test_earned_file_capability_ids_valid() -> None:
    """习得别名的 capability_id 同样必须落在 Excel 30 能力内。"""
    import json

    from backend.skills.resolver import load_earned

    caps_file = (
        Path(__file__).resolve().parents[1] / "data/processed/capability-matrix/capabilities.json"
    )
    if not caps_file.is_file():
        return
    caps = json.loads(caps_file.read_text(encoding="utf-8"))["capabilities"]
    valid = {c["capability_id"] for c in caps}
    for ea in load_earned():
        assert ea.capability_id in valid, ea.mention
