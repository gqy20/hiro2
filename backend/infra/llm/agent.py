"""Governed Agent Loop：工具调用循环 + 每步留痕 + token 预算硬闸门。

企业级约束（本模块存在的原因）：
- 审计：每次 LLM 调用与工具执行追加写 ``run_dir/agent-steps.jsonl``（append-only），
  含时间戳、prompt 版本、模型版本、token 增量与耗时；run 结束写 ``agent-run.json`` 摘要。
- 成本：TokenBudget 为硬上限，超限立即优雅终止（status=budget_exhausted），
  已消耗量仍完整留痕；预算应留出 headroom，本模块不做"最后再补一次调用"。
- 可靠：工具异常不崩溃，错误作为 tool_result(is_error) 回灌供 agent 自纠错；
  最终输出必须通过 Pydantic 校验，失败回灌错误重试一次，再失败终止。
- 边界：agent 只产出结构化候选（output_model 实例），不直接成为业务事实。

消息格式沿用 Anthropic Messages 原生 content blocks（dict），与 Provider 层一致。
"""

from __future__ import annotations

import asyncio
import json
import time
import traceback
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from .promptspec import PromptSpec
from .provider import UsageTotals

# ---------------------------------------------------------------- 值对象


class TokenBudget(BaseModel):
    """一次 agent 运行的 token 硬上限；None 表示该项不限。"""

    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None

    def exceeded(self, usage: UsageTotals) -> str | None:
        """返回超限原因；未超限返回 None。"""
        if self.input_tokens is not None and usage.input_tokens > self.input_tokens:
            return f"input_tokens {usage.input_tokens} > {self.input_tokens}"
        if self.output_tokens is not None and usage.output_tokens > self.output_tokens:
            return f"output_tokens {usage.output_tokens} > {self.output_tokens}"
        if self.total_tokens is not None and usage.total > self.total_tokens:
            return f"total_tokens {usage.total} > {self.total_tokens}"
        return None

    def as_dict(self) -> dict[str, int | None]:
        return self.model_dump()


class ToolSpec(BaseModel):
    """一个可被 agent 调用的工具：应用层用例的受控包装。

    func 签名：def func(**kwargs) -> Any；kwargs 已通过 args_model 校验。
    """

    model_config = {"arbitrary_types_allowed": True}

    name: str
    description: str
    args_model: type[BaseModel]
    func: Callable[..., Any]

    def anthropic_schema(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.args_model.model_json_schema(),
        }


class ChatTurn(BaseModel):
    """一次 chat 调用的归一化结果（Provider 无关）。"""

    text: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)  # {id,name,args}
    stop_reason: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


AgentStatus = Literal[
    "completed",
    "max_steps",
    "budget_exhausted",
    "schema_error",
    "provider_error",
]


class AgentResult(BaseModel):
    status: AgentStatus
    output: dict[str, Any] | None = None  # output_model 校验后的产物
    steps: int = 0  # LLM 调用次数
    usage: dict[str, int] = Field(default_factory=dict)
    budget: dict[str, int | None] | None = None
    error: str | None = None
    run_dir: str = ""


class AgentPorter(Protocol):
    """agent loop 依赖的最小协议；AnthropicProvider 与 MockChatProvider 均实现。"""

    name: str
    model_version: str
    usage: UsageTotals

    async def chat(
        self,
        *,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
        timeout: float = 60.0,
    ) -> ChatTurn: ...


# ---------------------------------------------------------------- 运行日志


class AgentRunLog:
    """append-only JSONL 留痕 + run 摘要。每行是一个独立 JSON 对象。"""

    def __init__(self, run_dir: Path, meta: dict[str, Any]) -> None:
        run_dir.mkdir(parents=True, exist_ok=True)
        self.steps_path = run_dir / "agent-steps.jsonl"
        self.meta = meta

    def _emit(self, record: dict[str, Any]) -> None:
        record = {"ts": datetime.now(UTC).isoformat(), **self.meta, **record}
        with self.steps_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def llm_call(
        self, step: int, turn: ChatTurn, latency_ms: int, budget_reason: str | None
    ) -> None:
        self._emit(
            {
                "kind": "llm_call",
                "step": step,
                "latency_ms": latency_ms,
                "input_tokens": turn.input_tokens,
                "output_tokens": turn.output_tokens,
                "stop_reason": turn.stop_reason,
                "tool_calls": turn.tool_calls,
                "text_preview": turn.text[:200],
                "budget_exceeded": budget_reason,
            }
        )

    def tool_result(
        self,
        step: int,
        name: str,
        args: dict[str, Any],
        ok: bool,
        error: str | None,
        result: Any,
        latency_ms: int,
    ) -> None:
        if isinstance(result, str):
            result_text = result
        else:
            result_text = json.dumps(result, ensure_ascii=False, default=str)
        self._emit(
            {
                "kind": "tool_result",
                "step": step,
                "tool": name,
                "args": args,
                "ok": ok,
                "error": error,
                "latency_ms": latency_ms,
                "result_chars": len(result_text),
                "result_preview": result_text[:200],
            }
        )

    def schema_retry(self, step: int, error: str) -> None:
        self._emit({"kind": "schema_retry", "step": step, "error": error[:500]})

    def provider_retry(self, step: int, error: str) -> None:
        self._emit({"kind": "provider_retry", "step": step, "error": error[:300]})

    def final(
        self,
        status: AgentStatus,
        steps: int,
        usage: UsageTotals,
        budget: TokenBudget | None,
        error: str | None,
    ) -> None:
        self._emit(
            {
                "kind": "run_end",
                "status": status,
                "steps": steps,
                "usage": usage.as_dict(),
                "budget": budget.as_dict() if budget else None,
                "error": error,
            }
        )

    def write_summary(self, result: AgentResult, task: str, budget: TokenBudget | None) -> None:
        """run 结束写一次性摘要快照，报表/前端直接读，不必扫描 jsonl。"""
        payload = {
            **self.meta,
            "status": result.status,
            "steps": result.steps,
            "task": task,
            "usage": result.usage,
            "budget": budget.as_dict() if budget else None,
            "error": result.error,
            "ts": datetime.now(UTC).isoformat(),
        }
        (self.steps_path.parent / "agent-run.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8"
        )


# ---------------------------------------------------------------- 主循环


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        first_newline = t.find("\n")
        t = t[first_newline + 1 :] if first_newline != -1 else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def _final_output(
    turn: ChatTurn, output_model: type[BaseModel]
) -> tuple[BaseModel | None, str | None]:
    """从 end_turn 文本解析 JSON 并校验；返回 (产物, 错误)。"""
    try:
        data = json.loads(_strip_fences(turn.text))
        return output_model.model_validate(data), None
    except Exception as exc:  # noqa: BLE001 - 校验失败统一回灌给 agent
        return None, f"{type(exc).__name__}: {exc}"


async def run_agent(
    *,
    porter: AgentPorter,
    spec: PromptSpec,
    tools: list[ToolSpec],
    task: str,
    output_model: type[BaseModel],
    run_dir: Path,
    max_steps: int = 8,
    budget: TokenBudget | None = None,
    exit_tool: str | None = None,
) -> AgentResult:
    """执行一个受治理的 agent 运行。

    spec.limits 提供 max_tokens / timeout_seconds；system prompt 来自 spec（版本留痕）。
    exit_tool：指定某个工具名为"提交出口"——模型调用它时，其参数即最终产物
    （过 output_model 校验后完成 run）。用于统一每轮响应为工具结构：
    部分网关在"工具调用 -> 纯文本长输出"的模式转换点会持续 422。
    """
    limits = spec.limits
    max_tokens = int(limits.get("max_tokens", 4096))
    timeout = float(limits.get("timeout_seconds", 60))

    run_usage = UsageTotals()
    log = AgentRunLog(
        run_dir,
        meta={
            "prompt_id": spec.id,
            "prompt_version": spec.version,
            "model": porter.model_version,
            "provider": porter.name,
        },
    )
    tool_map = {t.name: t for t in tools}
    messages: list[dict[str, Any]] = [{"role": "user", "content": task}]
    schema_failures = 0
    result = AgentResult(
        status="max_steps",
        run_dir=str(run_dir),
        budget=budget.as_dict() if budget else None,
    )

    def finish(
        status: AgentStatus,
        error: str | None = None,
        output: dict[str, Any] | None = None,
    ) -> AgentResult:
        result.status = status
        result.error = error
        result.output = output
        result.usage = run_usage.as_dict()
        log.final(status, result.steps, run_usage, budget, error)
        log.write_summary(result, task, budget)
        return result

    step = 0
    while step < max_steps:
        step += 1
        result.steps = step
        turn: ChatTurn | None = None
        for attempt in (1, 2):  # 网关偶发故障重试一次（失败请求通常不计费，留痕可见）
            started = time.monotonic()
            try:
                turn = await porter.chat(
                    system=spec.system,
                    messages=messages,
                    tools=[t.anthropic_schema() for t in tools],
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                break
            except Exception as exc:  # noqa: BLE001 - 两次失败才终止留痕，不无限重试烧钱
                tb = traceback.format_exc().strip().splitlines()
                detail = f"{type(exc).__name__}: {exc} | {tb[-1] if len(tb) > 1 else ''}"
                if attempt == 2:
                    return finish("provider_error", detail[:500])
                log.provider_retry(step, detail)
                await asyncio.sleep(1)
        assert turn is not None
        latency = int((time.monotonic() - started) * 1000)

        # token 记账：本次增量 + run 累计（provider.usage 是全局跨 run 累计，不用于预算）
        run_usage.add(turn.input_tokens, turn.output_tokens)
        budget_reason = budget.exceeded(run_usage) if budget else None
        log.llm_call(step, turn, latency, budget_reason)
        if budget_reason:
            return finish("budget_exhausted", f"token 预算超限: {budget_reason}")

        # 分支一：模型请求工具 -> 执行（异常回灌自纠错），结果进消息历史
        if turn.tool_calls:
            # 提交出口：exit_tool 的参数即最终产物（校验后完成），不再回灌
            if exit_tool and any(c.get("name") == exit_tool for c in turn.tool_calls):
                call = next(c for c in turn.tool_calls if c.get("name") == exit_tool)
                log.tool_result(step, exit_tool, call.get("args") or {}, True, None, "提交", 0)
                try:
                    output = output_model.model_validate(call.get("args") or {})
                except Exception as exc:  # noqa: BLE001 - 出口参数坏了回灌重来
                    log.schema_retry(step, f"{type(exc).__name__}: {exc}")
                    schema_failures += 1
                    if schema_failures >= 2:
                        return finish("schema_error", f"exit_tool 参数校验失败: {exc}")
                    messages.append(
                        {
                            "role": "assistant",
                            "content": [
                                {
                                    "type": "tool_use",
                                    "id": call.get("id", ""),
                                    "name": exit_tool,
                                    "input": call.get("args") or {},
                                }
                            ],
                        }
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "tool_result",
                                    "tool_use_id": call.get("id", ""),
                                    "content": (
                                        f"参数未通过 {output_model.__name__} 校验：{exc}。"
                                        f"请修正后重新调用 {exit_tool}。"
                                    ),
                                    "is_error": True,
                                }
                            ],
                        }
                    )
                    continue
                return finish("completed", output=output.model_dump())

            tool_results: list[dict[str, Any]] = []
            for call in turn.tool_calls:
                name, args = str(call.get("name", "")), call.get("args") or {}
                tool = tool_map.get(name)
                t0 = time.monotonic()
                if tool is None:
                    ok, error, value = False, f"未知工具: {name}", None
                else:
                    try:
                        checked = tool.args_model.model_validate(args)
                        ok, error, value = True, None, tool.func(**checked.model_dump())
                    except Exception as exc:  # noqa: BLE001 - 工具错误回灌，agent 可换路
                        ok, error, value = False, f"{type(exc).__name__}: {exc}", None
                log.tool_result(
                    step,
                    name,
                    args,
                    ok,
                    error,
                    value,
                    int((time.monotonic() - t0) * 1000),
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.get("id", ""),
                        "content": (
                            value
                            if isinstance(value, str)
                            else (
                                json.dumps(value, ensure_ascii=False, default=str)
                                if value is not None
                                else (error or "空结果")
                            )
                        ),
                        **({"is_error": True} if error else {}),
                    }
                )
            messages.append(
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": c.get("id", ""),
                            "name": c.get("name", ""),
                            "input": c.get("args") or {},
                        }
                        for c in turn.tool_calls
                    ],
                }
            )
            messages.append({"role": "user", "content": tool_results})
            continue

        # 分支二：模型给出最终答案 -> Pydantic 校验，失败回灌一次
        parsed, error = _final_output(turn, output_model)
        if parsed is not None:
            return finish("completed", output=parsed.model_dump())
        schema_failures += 1
        log.schema_retry(step, error or "未知解析错误")
        if schema_failures >= 2:
            return finish("schema_error", error)
        messages.append({"role": "assistant", "content": [{"type": "text", "text": turn.text}]})
        messages.append(
            {
                "role": "user",
                "content": (
                    f"输出未通过 schema 校验：{error}\n"
                    f"请修正后仅输出符合 {output_model.__name__} 的 JSON，不要调用工具。"
                ),
            }
        )

    return finish("max_steps", f"达到步数上限 {max_steps}")
