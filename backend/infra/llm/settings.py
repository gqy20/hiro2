"""LLM 运行时配置：从 .env 读取项目专属的 HIRO2_LLM_* 变量。

不使用 ANTHROPIC_* 命名——那是 Claude Code / Anthropic SDK 的保留环境变量，
进程环境会覆盖 .env 文件导致配置串线。协议为 Anthropic Messages，
网关地址与密钥只存在 .env。HIRO2_LLM_PROVIDER=mock 时使用离线 Mock，供测试与 CI。
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    hiro2_llm_provider: str = "anthropic"
    hiro2_llm_base_url: str | None = None
    hiro2_llm_model: str | None = None
    hiro2_llm_api_key: str | None = None

    @property
    def can_call_anthropic(self) -> bool:
        return bool(self.hiro2_llm_base_url and self.hiro2_llm_model and self.hiro2_llm_api_key)
