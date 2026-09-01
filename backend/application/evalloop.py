"""evalloop: 评测-修正飞轮——错误 case 聚类 + 分析智能体产出规则补丁建议。

闭环：evalset score -> 非 ACCEPT case 聚类 -> 分析智能体（读错误簇 + 现有规则，
复用 governed agent loop）-> RulePatchSuggestion 落盘 -> 人工审核应用（改
scripts/rolemap.py 常量，git 可 review）-> rolemap 重跑 -> evalcmp 固定样本对比。

治理边界：建议只是候选，agent 不改代码不重跑规则；负改进由 evalcmp 如实呈现并可回滚。
这层循环是发榜方"效果测评与闭环优化"方向的直接落地。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.infra.llm.agent import (
    AgentPorter,
    AgentResult,
    TokenBudget,
    ToolSpec,
    run_agent,
)
from backend.infra.llm.promptspec import load_prompt

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
RUNS = ROOT / "data" / "runs"
METRICS = ROOT / "evaluation" / "samples" / "metrics.json"


# ---------------------------------------------------------------- 产物模型


class ErrorPattern(BaseModel):
    """一个错误模式：多 case 共享的系统性原因。"""

    name: str
    n_cases: int
    description: str


class RulePatchSuggestion(BaseModel):
    """一条规则补丁建议；target 指向 rolemap.py 的具体规则常量或函数。"""

    target_rule: str  # 如 "TITLE_ALIASES" / "BIZ_SIGNALS" / "_family_override"
    change: str
    evidence_task_ids: list[str] = Field(default_factory=list)
    expected_gain: str
    risk: str


class AnalysisReport(BaseModel):
    """分析智能体的最终产物（run_agent 的 output_model）。"""

    layer: Literal["role", "domain", "event"]
    error_patterns: list[ErrorPattern] = Field(default_factory=list)
    suggestions: list[RulePatchSuggestion] = Field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------- 输入收集


def metrics_text(layer: str) -> str:
    """当前指标（metrics.json 由 evalset.py score 产出，禁止手工填写）。"""
    if not METRICS.is_file():
        return "（metrics.json 不存在，先跑 evalset.py score）"
    metrics = json.loads(METRICS.read_text(encoding="utf-8"))
    key = {"role": "role_mapping", "domain": "domain_judgment", "event": "event_extraction"}[layer]
    m = metrics.get(key) or {}
    return (
        f"{key}: accuracy={m.get('accuracy')} "
        f"({m.get('agree')}/{m.get('labeled')}, total {m.get('total')})"
    )


def _latest_audit_disagreements() -> dict[str, dict[str, Any]]:
    """最新一次抽检 run 的分歧（task_id -> agent 视角）；无则空。"""
    best: Path | None = None
    for cfg in sorted(RUNS.glob("*/config.json"), reverse=True):
        try:
            if json.loads(cfg.read_text(encoding="utf-8")).get("component") == "evalaudit":
                best = cfg.parent
                break
        except Exception:  # noqa: BLE001 - 坏目录跳过
            continue
    if best is None or not (best / "audit-summary.json").is_file():
        return {}
    summary = json.loads((best / "audit-summary.json").read_text(encoding="utf-8"))
    return {d["task_id"]: d for d in summary.get("disagreements", [])}


def collect_error_cases(layer: str) -> list[dict[str, Any]]:
    """当前指标下判错的 case（decision != ACCEPT），叠加抽检分歧视角。

    每条：task_id / title / 系统输出 / 判定 / 理由 / 抽检 agent 视角（如有）。
    """
    from backend.application.annotate import load_annotations
    from backend.application.evalaudit import LAYER_OF_PREFIX, _csv_rows

    annotations = load_annotations()
    disagreements = _latest_audit_disagreements()
    prefix = next(p for p, (lyr, _) in LAYER_OF_PREFIX.items() if lyr == layer)
    rows = _csv_rows(layer)
    cases: list[dict[str, Any]] = []
    for i, row in enumerate(rows):
        task_id = f"task-{prefix}-{i:03d}"
        ann = annotations.get(task_id)
        if ann is None or ann["decision"] == "ACCEPT":
            continue
        if layer == "role":
            output = f"{row['系统岗位id']}（method={row['method']}）"
        elif layer == "domain":
            output = f"is_ai_role={row['系统判定']}"
        else:
            output = f"类型={row['事件类型']} 分级={row['事实分级']}"
        case = {
            "task_id": task_id,
            "title": row.get("职位名") or row.get("标题"),
            "system_output": output,
            "verdict": ann["decision"],
            "verdict_reason": ann.get("rationale") or "",
        }
        if task_id in disagreements:
            d = disagreements[task_id]
            case["audit_agent_view"] = f"{d['agent_decision']}: {d['rationale']}"
        cases.append(case)
    return cases


def rule_snapshot() -> str:
    """当前规则层快照：TITLE_ALIASES / BIZ_SIGNALS / 关键逻辑摘要。"""
    try:
        from rolemap import BIZ_SIGNALS, TITLE_ALIASES

        aliases = "\n".join(f'"{k}" -> {v}' for k, v in TITLE_ALIASES.items())
        biz = "、".join(BIZ_SIGNALS)
        return (
            f"TITLE_ALIASES（别名 -> 标准岗位名，按序匹配，更具体的词须在前）：\n{aliases}\n\n"
            f"BIZ_SIGNALS（商务/管理信号，title 命中且 alias 指向技术岗时跳过该别名）：\n{biz}\n\n"
            "post_check：confidence<0.6 强制 unmatched；title 无技术/AI/别名词时不通过。\n"
            "_family_override：别名命中后高优先族（视觉/部署/安全）覆写泛别名。"
        )
    except Exception as exc:  # noqa: BLE001 - 规则不可读时提示 agent 基于案例提建议
        return f"（规则快照不可用：{exc}）"


# ---------------------------------------------------------------- 工具与分析


def build_analyze_tools() -> list[ToolSpec]:
    """分析工具：岗位详情按需查询 + 报告提交出口。

    错误簇与规则快照是必读材料，直接内联进任务文本（工具化只会增加轮次与网关
    暴露面）。最终报告通过 submit_report 工具提交而非纯文本输出：网关在
    "工具调用 -> 纯文本长输出"的模式转换点会持续 422，统一为工具结构绕开。
    """
    from backend.application.evalaudit import POOLS, PositionQuery

    def lookup_position(position_id: str) -> str:
        POOLS.load()
        assert POOLS.positions is not None
        pos = POOLS.positions.get(position_id)
        if pos is None:
            return f"未找到岗位 {position_id}"
        return json.dumps(
            {
                "position_id": pos["position_id"],
                "group": pos.get("group"),
                "name": pos["name"],
                "summary": (pos.get("summary") or "")[:300],
            },
            ensure_ascii=False,
        )

    def submit_report(**kwargs: Any) -> str:  # pragma: no cover - exit_tool 不真正执行
        return "已提交"

    return [
        ToolSpec(
            name="lookup_position",
            description="按 position_id 查标准岗位职责（判断错配时用）",
            args_model=PositionQuery,
            func=lookup_position,
        ),
        ToolSpec(
            name="submit_report",
            description="提交最终分析报告（唯一出口；完成分析后必须调用它，不要输出纯文本）",
            args_model=AnalysisReport,
            func=submit_report,
        ),
    ]


async def analyze_layer(
    porter: AgentPorter,
    layer: str,
    run_dir: Path,
    error_cases: list[dict[str, Any]] | None = None,
    *,
    budget: TokenBudget | None = None,
) -> tuple[AnalysisReport | None, AgentResult]:
    """跑一轮分析智能体；返回 (报告, run 结果)。"""
    cases = collect_error_cases(layer) if error_cases is None else error_cases
    spec = load_prompt("eval-analyze")
    cases_text = "\n".join(
        f"{c['task_id']} | {c['title']} | -> {c['system_output']} | {c['verdict']}"
        + (f" | 抽检:{c['audit_agent_view']}" if c.get("audit_agent_view") else "")
        for c in cases
    )
    task = (
        f"分析 {layer} 层的错误模式并提出规则补丁建议。\n"
        f"当前指标：{metrics_text(layer)}\n\n"
        f"全部判错 case（含抽检 agent 视角）：\n{cases_text}\n\n"
        f"当前规则层快照：\n{rule_snapshot()}\n\n"
        f"要求：归纳错误模式（至少 2 条 case 支持才算模式），只针对规则可修的系统性"
        f"错误提补丁建议（个案错误写进 summary）；需要核对岗位职责时用 lookup_position。"
    )
    result = await run_agent(
        porter=porter,
        spec=spec,
        tools=build_analyze_tools(),
        task=task,
        output_model=AnalysisReport,
        run_dir=run_dir,
        max_steps=6,
        budget=budget or TokenBudget(total_tokens=60000),
        exit_tool="submit_report",
    )
    report = AnalysisReport.model_validate(result.output) if result.output else None
    return report, result
