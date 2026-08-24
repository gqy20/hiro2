"""PromptSpec：加载 prompts/*.yml，校验 AGENTS.md 第 6 节要求的必备字段。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REQUIRED_KEYS = (
    "id",
    "version",
    "task",
    "system",
    "input_schema",
    "output_schema",
    "limits",
    "enabled",
)
PROMPTS_DIR = Path(__file__).resolve().parents[3] / "prompts"


class PromptSpec:
    def __init__(self, data: dict[str, Any]) -> None:
        missing = [k for k in REQUIRED_KEYS if k not in data]
        if missing:
            raise ValueError(f"Prompt 缺少必备字段: {missing}")
        if not isinstance(data["version"], int) or data["version"] < 1:
            raise ValueError(f"Prompt 版本必须是正整数: {data['version']!r}")
        self.id: str = data["id"]
        self.version: int = data["version"]
        self.task: str = data["task"]
        self.system: str = data["system"]
        self.input_schema: dict[str, Any] = data["input_schema"]
        self.output_schema: str = data["output_schema"]
        self.limits: dict[str, Any] = data["limits"]
        self.enabled: bool = data["enabled"]


def load_prompt(name: str, prompts_dir: Path = PROMPTS_DIR) -> PromptSpec:
    """按文件名（不含扩展名）加载 Prompt，例如 load_prompt("report-event")。"""
    path = prompts_dir / f"{name}.yml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    spec = PromptSpec(data)
    if not spec.enabled:
        raise ValueError(f"Prompt {name} 已停用 (enabled=false)")
    return spec
