"""评测抽检智能体测试：MockChatProvider 离线，不触真实 API、不依赖真实数据文件。

采样确定性、case 概要构建、单 case agent 复核全流程留痕、分歧识别。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.application.evalaudit import (  # noqa: E402
    AuditVerdict,
    Disagreement,
    audit_case,
    build_tools,
    find_disagreements,
    spotcheck_sample,
)
from backend.infra.llm.agent import ChatTurn  # noqa: E402
from backend.infra.llm.provider import MockChatProvider  # noqa: E402


def _anno(decision: str, rationale: str = "AI判定") -> dict:
    return {"decision": decision, "rationale": rationale}


def test_spotcheck_all_non_accept_plus_10pct_accept() -> None:
    """非 ACCEPT 全选；ACCEPT 抽 ceil(10%)；同 seed 结果一致。"""
    annotations = {
        f"task-role_level-{i:03d}": _anno("ACCEPT" if i < 100 else "REJECT") for i in range(110)
    }
    picked = spotcheck_sample(annotations, seed=1)
    non_accept = [t for t in picked if annotations[t]["decision"] != "ACCEPT"]
    accepts = [t for t in picked if annotations[t]["decision"] == "ACCEPT"]
    assert len(non_accept) == 10  # 全选
    assert len(accepts) == 10  # ceil(100 * 0.1)
    assert picked == spotcheck_sample(annotations, seed=1)  # 可复现
    assert set(picked) <= set(annotations)


def test_case_summary_contains_system_output_and_prelabel(monkeypatch) -> None:
    """case 文本包含系统输出、预标注判定与查证指引。"""
    import backend.application.evalaudit as ea

    rows = [
        {"jd_id": "bd:1", "职位名": "大模型算法工程师", "系统岗位id": "pos_01", "method": "exact"}
    ] * 5
    monkeypatch.setattr(ea, "_csv_rows", lambda layer: rows)
    text = ea.case_summary("task-role_level-003", _anno("ACCEPT", "映射正确"))
    assert "task-role_level-003" in text and "role" in text
    assert "pos_01" in text and "exact" in text
    assert "ACCEPT" in text and "映射正确" in text
    assert "查证" in text  # 要求先查证再判定（工具细则在 system prompt）


def _tools_stub() -> list:
    return build_tools()


def test_audit_case_full_flow_with_audit_trail(tmp_path: Path, monkeypatch) -> None:
    """单 case 复核：工具调用 -> 最终判定，每步留痕 + verdict 校验。"""
    import backend.application.evalaudit as ea

    rows = [
        {"jd_id": "bd:1", "职位名": "视觉大模型算法工程师", "系统岗位id": "pos_01", "method": "llm"}
    ] * 5
    monkeypatch.setattr(ea, "_csv_rows", lambda layer: rows)
    # 工具数据池打桩：pos_01 与一条 JD，避免依赖真实数据文件
    monkeypatch.setattr(
        ea.POOLS,
        "load",
        lambda: (
            setattr(
                ea.POOLS,
                "positions",
                {
                    "pos_01": {
                        "position_id": "pos_01",
                        "group": "AI研发",
                        "name": "大模型算法工程师",
                        "summary": "负责LLM训练",
                    }
                },
            ),
            setattr(
                ea.POOLS,
                "parsed",
                {
                    "bd:1": {
                        "title": "视觉大模型算法工程师",
                        "is_ai_role": True,
                        "domain_reason": "CV+LLM",
                        "responsibilities": ["大模型训练"],
                        "skill_mentions": ["PyTorch"],
                        "unresolved": [],
                    }
                },
            ),
            setattr(ea.POOLS, "events", {}),
        ),
    )

    final = json.dumps(
        {
            "task_id": "task-role_level-000",
            "layer": "role",
            "agent_decision": "ACCEPT",
            "rationale": "职责为LLM训练，与pos_01一致",
            "error_type": None,
        },
        ensure_ascii=False,
    )
    porter = MockChatProvider(
        [
            ChatTurn(
                stop_reason="tool_use",
                tool_calls=[
                    {"id": "t1", "name": "lookup_position", "args": {"position_id": "pos_01"}}
                ],
            ),
            ChatTurn(stop_reason="end_turn", text=final, input_tokens=200, output_tokens=80),
        ]
    )
    verdict, result = asyncio.run(
        audit_case(porter, "task-role_level-000", _anno("ACCEPT"), tmp_path / "c1")
    )
    assert result.status == "completed"
    assert verdict is not None and verdict.agent_decision == "ACCEPT"
    assert verdict.layer == "role"

    steps = [
        json.loads(line)
        for line in (tmp_path / "c1" / "agent-steps.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    kinds = [s["kind"] for s in steps]
    assert kinds == ["llm_call", "tool_result", "llm_call", "run_end"]
    tool_row = steps[1]
    assert tool_row["tool"] == "lookup_position"
    assert "大模型算法工程师" in tool_row["result_preview"]  # 工具真实查到了打桩数据
    assert steps[2]["output_tokens"] == 80  # token 留痕


def test_find_disagreements_flags_conflicts() -> None:
    """agent 判定与预标注不一致（含 UNKNOWN）即分歧。"""
    annotations = {
        "task-role_level-000": _anno("ACCEPT"),
        "task-evidence_audit-001": _anno("REJECT"),
        "task-skill_mapping-002": _anno("ACCEPT"),
    }
    verdicts = [
        AuditVerdict(
            task_id="task-role_level-000",
            layer="role",
            agent_decision="REJECT",
            rationale="职责不符",
            error_type="岗位错配",
        ),
        AuditVerdict(
            task_id="task-evidence_audit-001",
            layer="domain",
            agent_decision="REJECT",
            rationale="确实非AI",
        ),
        AuditVerdict(
            task_id="task-skill_mapping-002",
            layer="event",
            agent_decision="UNKNOWN",
            rationale="证据不足",
        ),
    ]
    dis = find_disagreements(verdicts, annotations)
    ids = [d.task_id for d in dis]
    assert ids == ["task-role_level-000", "task-skill_mapping-002"]
    assert dis[0].prelabel_decision == "ACCEPT" and dis[0].agent_decision == "REJECT"
    assert isinstance(dis[0], Disagreement) and dis[0].error_type == "岗位错配"
