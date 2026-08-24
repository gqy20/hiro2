"""LLM Provider 适配层：Anthropic Messages 协议 + 离线 Mock。

领域代码只依赖 LLMPorter 协议，不直接导入 anthropic SDK。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .settings import LLMSettings


@dataclass
class UsageTotals:
    """一次运行内累计的 API token 消耗（含重试）。"""

    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "calls": self.calls,
        }

    def add(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1


class LLMProvider(Protocol):
    """最小协议：一次 system+user 文本调用，返回纯文本；usage 记录累计消耗。"""

    name: str
    model_version: str
    usage: UsageTotals

    async def complete(
        self, *, system: str, user: str, max_tokens: int, timeout: float = 60.0
    ) -> str: ...


class AnthropicProvider:
    """Anthropic Messages 协议适配器，网关地址与密钥来自 .env 的 HIRO2_LLM_*。"""

    def __init__(self, settings: LLMSettings) -> None:
        from anthropic import AsyncAnthropic

        if not settings.can_call_anthropic:
            raise ValueError("HIRO2_LLM_BASE_URL/MODEL/API_KEY 未配置完整，无法创建 Provider")
        self._client = AsyncAnthropic(
            base_url=settings.hiro2_llm_base_url,
            api_key=settings.hiro2_llm_api_key,
        )
        self._model = settings.hiro2_llm_model or ""
        self.name = "anthropic"
        self.model_version = self._model
        self.usage = UsageTotals()

    async def complete(
        self, *, system: str, user: str, max_tokens: int, timeout: float = 60.0
    ) -> str:
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            timeout=timeout,
        )
        if resp.usage is not None:
            self.usage.add(
                input_tokens=resp.usage.input_tokens or 0,
                output_tokens=resp.usage.output_tokens or 0,
            )
        return "".join(getattr(block, "text", "") for block in resp.content)


class MockProvider:
    """离线假实现：按调用轮次返回预设响应，用于测试与 CI。"""

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self._calls = 0
        self.name = "mock"
        self.model_version = "mock-1"
        self.usage = UsageTotals()

    async def complete(
        self, *, system: str, user: str, max_tokens: int, timeout: float = 60.0
    ) -> str:
        if self._calls >= len(self._responses):
            return self._responses[-1]
        resp = self._responses[self._calls]
        self._calls += 1
        return resp


def build_provider(settings: LLMSettings, mock_responses: list[str] | None = None) -> LLMProvider:
    """按配置选择 Provider：mock 优先显式指定，否则 Anthropic。"""
    if settings.hiro2_llm_provider == "mock":
        return MockProvider(mock_responses or ['{"events": []}'])
    return AnthropicProvider(settings)
