"""LLM 基础设施与事件抽取服务测试：全部使用 MockProvider，不触真实 API。"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.infra.llm.promptspec import PromptSpec, load_prompt  # noqa: E402
from backend.infra.llm.provider import MockProvider, build_provider  # noqa: E402
from backend.infra.llm.settings import LLMSettings  # noqa: E402
from backend.temporal.models import ReportEventList  # noqa: E402
from backend.temporal.service import Article, extract_events, extract_one  # noqa: E402

GOOD_EVENT = (
    '{"event_type": "model_release", "title": "X 发布", "summary": "公司 X 发布了新模型",'
    ' "entities": ["X"], "fact_grade": "fact", "urls": [], "skill_mentions": ["推理"]}'
)
GOOD = '{"events": [' + GOOD_EVENT + "]}"


def make_spec(tmp_path: Path, **overrides: object) -> PromptSpec:
    data = {
        "id": "t",
        "version": 1,
        "task": "测试抽取",
        "system": "sys",
        "input_schema": {},
        "output_schema": "ReportEventList",
        "limits": {"max_tokens": 100, "timeout_seconds": 5},
        "enabled": True,
    }
    data.update(overrides)
    path = tmp_path / "t.yml"
    path.write_text(yaml.safe_dump(data), encoding="utf-8")
    return load_prompt("t", prompts_dir=tmp_path)


def test_promptspec_requires_fields(tmp_path: Path) -> None:
    data = {"id": "t", "version": 1}
    (tmp_path / "bad.yml").write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(ValueError, match="缺少必备字段"):
        load_prompt("bad", prompts_dir=tmp_path)
    with pytest.raises(ValueError, match="版本"):
        make_spec(tmp_path, version="1")


def test_official_prompt_loads() -> None:
    spec = load_prompt("report-event")
    assert spec.version >= 1 and spec.enabled
    assert spec.output_schema == "ReportEventList"


def test_extract_one_ok(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    provider = MockProvider([f"```json\n{GOOD}\n```"])  # 故意带代码围栏
    article = Article(
        item_id="a:1", title="早报", published_at="2026-08-21", text="# 早报\nX 发布了新模型"
    )
    events, error = extract_one_sync(spec, provider, article)
    assert error is None and len(events) == 1
    e = events[0]
    assert e.event_id == "a:1:e001" and e.item_id == "a:1"
    assert e.prompt_version == 1 and e.model_version == "mock-1"


def extract_one_sync(spec, provider, article):
    import asyncio

    return asyncio.run(extract_one(spec, provider, article))


def test_extract_retry_then_quarantine(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    # 1+2 次全部输出非法 JSON -> 隔离，绝不静默接受
    provider = MockProvider(["不是 JSON", "还是不合法", '{"broken": true}'])
    article = Article(item_id="a:2", title="t", published_at=None, text="正文")
    events, error = extract_one_sync(spec, provider, article)
    assert events == [] and error is not None


def test_extract_retry_recovers(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    provider = MockProvider(["坏输出", GOOD])  # 第一次失败，重试成功
    article = Article(item_id="a:3", title="t", published_at="2026-08-01", text="正文")
    events, error = extract_one_sync(spec, provider, article)
    assert error is None and len(events) == 1


def test_extract_events_batch_and_log(tmp_path: Path) -> None:
    spec = make_spec(tmp_path)
    provider = MockProvider([GOOD])  # 循环复用最后一个响应
    articles = [
        Article(item_id=f"a:{i}", title="t", published_at=None, text="正文") for i in range(5)
    ]

    class RunStub:
        logs: list[str] = []

        def log(self, *args: object, **kw: object) -> None:
            RunStub.logs.append(str(args))

    import asyncio

    result = asyncio.run(extract_events(articles, spec, provider, RunStub()))
    assert len(result.events) == 5 and result.quarantined == []


def test_extract_api_error_quarantined(tmp_path: Path) -> None:
    """网关持续超时/异常 -> 进隔离队列且 error_type=api_error，不炸整批。"""

    class ExplodingProvider(MockProvider):
        async def complete(self, **kw: object) -> str:
            raise TimeoutError("gateway timeout")

    spec = make_spec(tmp_path)
    provider = ExplodingProvider([])
    article = Article(item_id="a:9", title="t", published_at=None, text="正文")
    events, error = extract_one_sync(spec, provider, article)
    assert events == [] and error is not None
    assert error[0] == "api_error" and "TimeoutError" in error[1]


def test_build_provider_mock_settings() -> None:
    settings = LLMSettings(hiro2_llm_provider="mock")
    provider = build_provider(settings, [GOOD])
    assert provider.name == "mock"
    assert provider.usage.as_dict() == {"input_tokens": 0, "output_tokens": 0, "calls": 0}


def test_model_validation_rejects_bad_enum() -> None:
    with pytest.raises(ValueError):
        ReportEventList.model_validate(
            {"events": [{"event_type": "其他", "title": "t", "summary": "s", "fact_grade": "fact"}]}
        )
