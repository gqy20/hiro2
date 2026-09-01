"""Governed Agent Loop 测试：全部走 MockChatProvider，不触真实 API。

重点覆盖企业级约束：每步留痕完整性、token 记账、预算硬闸门、
工具异常回灌自纠错、schema 校验重试。项目惯例：同步测试内 asyncio.run。
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import BaseModel  # noqa: E402

from backend.infra.llm.agent import (  # noqa: E402
    ChatTurn,
    TokenBudget,
    ToolSpec,
    run_agent,
)
from backend.infra.llm.promptspec import load_prompt  # noqa: E402
from backend.infra.llm.provider import MockChatProvider  # noqa: E402


class EchoArgs(BaseModel):
    text: str


class ReportOut(BaseModel):
    verdict: str
    reasons: list[str]


def make_spec(tmp_path: Path) -> Any:
    data = {
        "id": "agent-test",
        "version": 1,
        "task": "测试智能体",
        "system": "你是测试智能体",
        "input_schema": {},
        "output_schema": "ReportOut",
        "limits": {"max_tokens": 512, "timeout_seconds": 5},
        "enabled": True,
    }
    (tmp_path / "agent-test.yml").write_text(yaml.safe_dump(data), encoding="utf-8")
    return load_prompt("agent-test", prompts_dir=tmp_path)


def tool_turn(name: str, args: dict[str, Any], tid: str = "t1", **tokens: int) -> ChatTurn:
    return ChatTurn(
        stop_reason="tool_use",
        tool_calls=[{"id": tid, "name": name, "args": args}],
        input_tokens=tokens.get("input_tokens", 100),
        output_tokens=tokens.get("output_tokens", 10),
    )


def final_turn(text: str, **tokens: int) -> ChatTurn:
    return ChatTurn(
        stop_reason="end_turn",
        text=text,
        input_tokens=tokens.get("input_tokens", 100),
        output_tokens=tokens.get("output_tokens", 50),
    )


def read_steps(run_dir: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in (run_dir / "agent-steps.jsonl").read_text(encoding="utf-8").splitlines()
    ]


def echo_tool(func: Any) -> ToolSpec:
    return ToolSpec(name=func.__name__, description="测试工具", args_model=EchoArgs, func=func)


def test_tool_loop_completes_with_full_audit_trail(tmp_path: Path) -> None:
    """两步工具调用后给出最终答案：steps.jsonl 完整记录每次调用与工具结果。"""
    porter = MockChatProvider(
        [
            tool_turn("echo", {"text": "hi"}),
            tool_turn("echo", {"text": "again"}, tid="t2"),
            final_turn('{"verdict": "agree", "reasons": ["工具结果一致"]}'),
        ]
    )
    calls: list[str] = []

    def echo(text: str) -> str:
        calls.append(text)
        return f"echo:{text}"

    result = asyncio.run(
        run_agent(
            porter=porter,
            spec=make_spec(tmp_path),
            tools=[echo_tool(echo)],
            task="检查一致性",
            output_model=ReportOut,
            run_dir=tmp_path / "run1",
            max_steps=6,
        )
    )
    assert result.status == "completed"
    assert result.output == {"verdict": "agree", "reasons": ["工具结果一致"]}
    assert result.steps == 3
    assert calls == ["hi", "again"]

    steps = read_steps(tmp_path / "run1")
    kinds = [s["kind"] for s in steps]
    # 每步一对 llm_call + tool_result，最后一次是 llm_call + run_end
    assert kinds == ["llm_call", "tool_result"] * 2 + ["llm_call", "run_end"]
    llm_rows = [s for s in steps if s["kind"] == "llm_call"]
    assert all("input_tokens" in s and "latency_ms" in s for s in llm_rows)
    tool_rows = [s for s in steps if s["kind"] == "tool_result"]
    assert [t["tool"] for t in tool_rows] == ["echo", "echo"]
    assert all(t["ok"] is True and "result_preview" in t for t in tool_rows)

    # run 摘要可独立读取：版本、模型、token、状态齐全
    summary = json.loads((tmp_path / "run1" / "agent-run.json").read_text(encoding="utf-8"))
    assert summary["status"] == "completed"
    assert summary["prompt_id"] == "agent-test" and summary["prompt_version"] == 1
    assert summary["model"] == "mock-chat-1"
    assert summary["usage"] == {"input_tokens": 300, "output_tokens": 70, "calls": 3}


def test_budget_hard_gate_stops_and_logs_spend(tmp_path: Path) -> None:
    """token 预算是硬闸门：超限立即终止，已消耗量完整留痕。"""
    porter = MockChatProvider(
        [tool_turn("echo", {"text": "a"}, input_tokens=600, output_tokens=20)]
    )

    def echo(text: str) -> str:
        return text

    result = asyncio.run(
        run_agent(
            porter=porter,
            spec=make_spec(tmp_path),
            tools=[echo_tool(echo)],
            task="任务",
            output_model=ReportOut,
            run_dir=tmp_path / "run2",
            max_steps=5,
            budget=TokenBudget(input_tokens=500),
        )
    )
    assert result.status == "budget_exhausted"
    assert result.output is None
    assert result.usage["input_tokens"] == 600  # 花了多少记多少
    steps = read_steps(tmp_path / "run2")
    assert steps[-1]["kind"] == "run_end"
    assert steps[-1]["status"] == "budget_exhausted"
    assert steps[0]["budget_exceeded"]  # 超限当步即标记


def test_max_steps_terminates(tmp_path: Path) -> None:
    """持续请求工具的 run 被步数上限兜住。"""

    def echo(text: str) -> str:
        return text

    porter = MockChatProvider([tool_turn("echo", {"text": "x"})])  # 恒定工具调用
    result = asyncio.run(
        run_agent(
            porter=porter,
            spec=make_spec(tmp_path),
            tools=[echo_tool(echo)],
            task="任务",
            output_model=ReportOut,
            run_dir=tmp_path / "run3",
            max_steps=3,
        )
    )
    assert result.status == "max_steps"
    assert result.steps == 3


def test_tool_error_feeds_back_and_agent_recovers(tmp_path: Path) -> None:
    """工具异常不崩溃：错误回灌，agent 换正确参数后自纠错。"""
    porter = MockChatProvider(
        [
            tool_turn("pick", {"text": ""}),  # 首次参数非法 -> 校验/执行失败
            final_turn('{"verdict": "ok", "reasons": []}'),
        ]
    )

    def pick(text: str) -> str:
        if not text:
            raise ValueError("text 不能为空")
        return text

    tool = ToolSpec(name="pick", description="取文本", args_model=EchoArgs, func=pick)
    result = asyncio.run(
        run_agent(
            porter=porter,
            spec=make_spec(tmp_path),
            tools=[tool],
            task="任务",
            output_model=ReportOut,
            run_dir=tmp_path / "run4",
            max_steps=4,
        )
    )
    assert result.status == "completed"
    steps = read_steps(tmp_path / "run4")
    failed = [s for s in steps if s["kind"] == "tool_result" and not s["ok"]]
    assert len(failed) == 1
    assert "text 不能为空" in failed[0]["error"]


def test_schema_retry_once_then_succeeds(tmp_path: Path) -> None:
    """最终输出校验失败回灌一次错误；修正后通过。"""
    porter = MockChatProvider(
        [
            final_turn('{"verdict": "ok" }', output_tokens=10),  # 缺 reasons
            final_turn('{"verdict": "ok", "reasons": ["补齐"]}', output_tokens=20),
        ]
    )
    result = asyncio.run(
        run_agent(
            porter=porter,
            spec=make_spec(tmp_path),
            tools=[],
            task="任务",
            output_model=ReportOut,
            run_dir=tmp_path / "run5",
            max_steps=4,
        )
    )
    assert result.status == "completed"
    steps = read_steps(tmp_path / "run5")
    retry = [s for s in steps if s["kind"] == "schema_retry"]
    assert len(retry) == 1 and "reasons" in retry[0]["error"]


def test_schema_error_after_two_failures(tmp_path: Path) -> None:
    """两次校验失败终止为 schema_error，不无限重试。"""
    porter = MockChatProvider([final_turn("不是JSON")])  # 恒定坏输出
    result = asyncio.run(
        run_agent(
            porter=porter,
            spec=make_spec(tmp_path),
            tools=[],
            task="任务",
            output_model=ReportOut,
            run_dir=tmp_path / "run6",
            max_steps=6,
        )
    )
    assert result.status == "schema_error"
    assert result.output is None


def test_unknown_tool_logged_and_continues(tmp_path: Path) -> None:
    """幻觉工具名（未注册）回灌错误，run 仍可正常收敛。"""
    porter = MockChatProvider(
        [
            tool_turn("nonexistent", {"x": 1}),
            final_turn('{"verdict": "ok", "reasons": []}'),
        ]
    )
    result = asyncio.run(
        run_agent(
            porter=porter,
            spec=make_spec(tmp_path),
            tools=[],
            task="任务",
            output_model=ReportOut,
            run_dir=tmp_path / "run7",
            max_steps=4,
        )
    )
    assert result.status == "completed"
    steps = read_steps(tmp_path / "run7")
    bad = [s for s in steps if s["kind"] == "tool_result"][0]
    assert bad["ok"] is False and "未知工具" in bad["error"]


def test_exit_tool_submits_output(tmp_path: Path) -> None:
    """exit_tool：模型调用提交工具即完成，参数过 output_model 校验。"""
    from backend.infra.llm.agent import ToolSpec

    class SumOut(BaseModel):
        answer: int

    class SumArgs(BaseModel):
        answer: int

    def submit(**kw: object) -> str:  # pragma: no cover - exit_tool 不真正执行
        return "已提交"

    tool = ToolSpec(name="submit", description="提交", args_model=SumArgs, func=submit)
    porter = MockChatProvider(
        [
            ChatTurn(
                stop_reason="tool_use",
                tool_calls=[{"id": "s1", "name": "submit", "args": {"answer": 42}}],
            )
        ]
    )
    result = asyncio.run(
        run_agent(
            porter=porter,
            spec=make_spec(tmp_path),
            tools=[tool],
            task="任务",
            output_model=SumOut,
            run_dir=tmp_path / "exit1",
            exit_tool="submit",
        )
    )
    assert result.status == "completed"
    assert result.output == {"answer": 42}


def test_exit_tool_bad_args_retry_then_fail(tmp_path: Path) -> None:
    """exit_tool 参数校验失败回灌一次；再失败终止 schema_error。"""
    from backend.infra.llm.agent import ToolSpec

    class SumOut(BaseModel):
        answer: int

    def submit(**kw: object) -> str:  # pragma: no cover
        return "已提交"

    tool = ToolSpec(name="submit", description="提交", args_model=SumOut, func=submit)
    porter = MockChatProvider(
        [
            ChatTurn(
                stop_reason="tool_use",
                tool_calls=[{"id": "s1", "name": "submit", "args": {"wrong": 1}}],
            ),
            ChatTurn(
                stop_reason="tool_use",
                tool_calls=[{"id": "s2", "name": "submit", "args": {"wrong": 2}}],
            ),
        ]
    )
    result = asyncio.run(
        run_agent(
            porter=porter,
            spec=make_spec(tmp_path),
            tools=[tool],
            task="任务",
            output_model=SumOut,
            run_dir=tmp_path / "exit2",
            exit_tool="submit",
        )
    )
    assert result.status == "schema_error"
    steps = read_steps(tmp_path / "exit2")
    assert sum(1 for s in steps if s["kind"] == "schema_retry") == 2
