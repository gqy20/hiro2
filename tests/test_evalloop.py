"""评测-修正飞轮测试：MockChatProvider 离线，不触真实 API。

覆盖：错误 case 收集（含抽检视角叠加）、规则快照可读、分析智能体全流程留痕、
产物模型校验。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import backend.application.evalloop as el  # noqa: E402
from backend.infra.llm.agent import ChatTurn  # noqa: E402
from backend.infra.llm.provider import MockChatProvider  # noqa: E402


def test_collect_error_cases_merges_audit_view(monkeypatch) -> None:
    """非 ACCEPT case 全收集；有抽检分歧的 case 叠加 agent 视角。"""
    rows = [
        {"jd_id": "bd:1", "职位名": "产品经理", "系统岗位id": "pos_01", "method": "alias"},
        {"jd_id": "bd:2", "职位名": "算法工程师", "系统岗位id": "pos_01", "method": "exact"},
    ]
    monkeypatch.setattr(
        el,
        "_latest_audit_disagreements",
        lambda: {"task-role_level-000": {"agent_decision": "REJECT", "rationale": "应为pos_06"}},
    )
    monkeypatch.setattr(
        "backend.application.annotate.load_annotations",
        lambda: {
            "task-role_level-000": {"decision": "MODIFY", "rationale": "映射偏差"},
            "task-role_level-001": {"decision": "ACCEPT", "rationale": "正确"},
        },
    )
    monkeypatch.setattr("backend.application.evalaudit._csv_rows", lambda layer: rows)
    cases = el.collect_error_cases("role")
    assert len(cases) == 1  # ACCEPT 不进错误集
    c = cases[0]
    assert c["task_id"] == "task-role_level-000"
    assert c["verdict"] == "MODIFY"
    assert "pos_06" in c["audit_agent_view"]  # 抽检视角叠加
    assert "pos_01" in c["system_output"]


def test_rule_snapshot_reads_live_constants() -> None:
    """规则快照能读到 rolemap.py 真实常量（TITLE_ALIASES/BIZ_SIGNALS）。"""
    snap = el.rule_snapshot()
    assert "TITLE_ALIASES" in snap
    assert "产品经理" in snap  # 现有别名之一
    assert "BIZ_SIGNALS" in snap


def test_analyze_layer_full_flow(tmp_path: Path, monkeypatch) -> None:
    """分析智能体全流程：内联输入 -> 按需查岗 -> 报告，每步留痕 + 产物校验。"""
    cases = [
        {
            "task_id": "task-role_level-000",
            "title": "QQ-Agent产品经理",
            "system_output": "pos_02（method=alias）",
            "verdict": "MODIFY",
            "verdict_reason": "应为产品岗",
        },
        {
            "task_id": "task-role_level-003",
            "title": "AI平台产品经理",
            "system_output": "pos_01（method=alias）",
            "verdict": "REJECT",
            "verdict_reason": "产品岗被映射算法岗",
        },
    ]
    report_json = json.dumps(
        {
            "layer": "role",
            "error_patterns": [
                {
                    "name": "产品经理别名被技术别名压制",
                    "n_cases": 2,
                    "description": "产品岗被 Agent/大模型别名抢先命中",
                }
            ],
            "suggestions": [
                {
                    "target_rule": "TITLE_ALIASES",
                    "change": "产品经理相关 title 优先匹配 pos_06，先于技术别名",
                    "evidence_task_ids": ["task-role_level-000", "task-role_level-003"],
                    "expected_gain": "约 +2 条命中",
                    "risk": "低",
                }
            ],
            "summary": "产品岗错配是最大错误面，先修别名优先级",
        },
        ensure_ascii=False,
    )
    porter = MockChatProvider(
        [
            ChatTurn(
                stop_reason="tool_use",
                tool_calls=[
                    {"id": "t1", "name": "lookup_position", "args": {"position_id": "pos_06"}}
                ],
            ),
            ChatTurn(
                stop_reason="end_turn", text=report_json, input_tokens=3000, output_tokens=500
            ),
        ]
    )
    report, result = asyncio.run(
        el.analyze_layer(porter, "role", tmp_path / "role", error_cases=cases)
    )
    assert result.status == "completed"
    assert report is not None
    assert report.layer == "role"
    assert len(report.error_patterns) == 1
    s = report.suggestions[0]
    assert s.target_rule == "TITLE_ALIASES" and len(s.evidence_task_ids) == 2

    # 留痕：一次查岗 + 最终输出 + run_end；内联输入在首条 llm_call 前
    steps = [
        json.loads(x)
        for x in (tmp_path / "role" / "agent-steps.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    tools = [r["tool"] for r in steps if r["kind"] == "tool_result"]
    assert tools == ["lookup_position"]
    assert steps[-1]["kind"] == "run_end" and steps[-1]["status"] == "completed"
