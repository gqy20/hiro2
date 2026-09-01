"""evalaudit: 评测抽检智能体——对 AI 预标注判定做独立二次判定，标记分歧供人工复核。

抽检策略（competition.md 行动清单）：非 ACCEPT 判定全复核 + ACCEPT 抽 10%，
固定 seed 可复现。每条 case 一个独立 agent run（独立留痕、独立 token 预算），
产物为分歧报告：agent 判定与 ai-prelabel-batch 判定不一致的 case 即人工优先复核对象。

边界：agent 判定只是候选，不写入 annotations.jsonl，不参与 score 计算；
正式指标仍以人工确认为准（评测纪律见 evaluation.md）。
"""

from __future__ import annotations

import csv
import json
import math
import random
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from backend.infra.llm.agent import (
    AgentPorter,
    AgentResult,
    TokenBudget,
    ToolSpec,
    run_agent,
)
from backend.infra.llm.promptspec import PromptSpec, load_prompt

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "evaluation" / "samples"
ROLEMAP = ROOT / "data" / "processed" / "jd-opencli" / "jd-role-map-repaired.jsonl"
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
EVENTS = ROOT / "data" / "processed" / "wechat-mp" / "events.jsonl"
POSITIONS = ROOT / "data" / "processed" / "capability-matrix" / "positions.jsonl"

SPOTCHECK = SAMPLES / "audit-spotcheck.json"
SPOTCHECK_SEED = 20260831
ACCEPT_RATE = 0.1

# task_id 前缀 -> (评测层, 冻结样本 CSV, 判定说明)；映射与 evalset.py _score_csv 一致
LAYER_OF_PREFIX = {
    "role_level": ("role", "role-mapping.csv"),
    "evidence_audit": ("domain", "domain-judgment.csv"),
    "skill_mapping": ("event", "event-extraction.csv"),
}

# 按层裁剪工具：role 不需要事件、domain/event 不需要岗位目录——防跑偏并省 token
LAYER_TOOLS = {
    "role": {"lookup_position", "lookup_jd"},  # 目录已内联进 case 文本
    "domain": {"lookup_jd"},
    "event": {"lookup_event"},
}


class AuditVerdict(BaseModel):
    """单 case 的 agent 复核判定（run_agent 的 output_model）。"""

    task_id: str
    layer: Literal["role", "domain", "event"]
    agent_decision: Literal["ACCEPT", "REJECT", "UNKNOWN"]
    rationale: str = ""
    error_type: str | None = None


class Disagreement(BaseModel):
    """agent 判定与预标注不一致的 case——人工优先复核对象。"""

    task_id: str
    layer: str
    prelabel_decision: str
    agent_decision: str
    rationale: str
    error_type: str | None = None


# ---------------------------------------------------------------- 抽检采样


def spotcheck_sample(
    annotations: dict[str, dict[str, Any]],
    *,
    seed: int = SPOTCHECK_SEED,
    accept_rate: float = ACCEPT_RATE,
) -> list[str]:
    """非 ACCEPT 全选 + ACCEPT 按 accept_rate 抽样；返回有序 task_id 清单。"""
    non_accept = sorted(t for t, a in annotations.items() if a["decision"] != "ACCEPT")
    accepts = sorted(t for t, a in annotations.items() if a["decision"] == "ACCEPT")
    k = math.ceil(len(accepts) * accept_rate)
    rng = random.Random(seed)
    picked = non_accept + sorted(rng.sample(accepts, k)) if k else non_accept
    return sorted(picked)


def write_spotcheck(task_ids: list[str]) -> Path:
    """写抽检清单（带 seed 与数量，可复现审计）。"""
    payload = {
        "dataset_version": "eval-v3-20260828",
        "seed": SPOTCHECK_SEED,
        "accept_rate": ACCEPT_RATE,
        "n": len(task_ids),
        "task_ids": task_ids,
    }
    SPOTCHECK.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return SPOTCHECK


def load_spotcheck() -> list[str]:
    payload = json.loads(SPOTCHECK.read_text(encoding="utf-8"))
    return list(payload["task_ids"])


# ---------------------------------------------------------------- 数据池与工具


class _DataPools:
    """三个只读数据池，懒加载一次（CLI 进程内共享）。"""

    def __init__(self) -> None:
        self.positions: dict[str, dict[str, Any]] | None = None
        self.parsed: dict[str, dict[str, Any]] | None = None
        self.events: dict[str, dict[str, Any]] | None = None

    def load(self) -> None:
        if self.positions is None:
            self.positions = {
                r["position_id"]: r
                for r in (json.loads(x) for x in POSITIONS.open(encoding="utf-8"))
            }
        if self.parsed is None:
            self.parsed = {
                r["jd_id"]: r for r in (json.loads(x) for x in PARSED.open(encoding="utf-8"))
            }
        if self.events is None:
            self.events = {
                r["event_id"]: r
                for r in (json.loads(x) for x in EVENTS.open(encoding="utf-8"))
                if r.get("is_primary", True)
            }


POOLS = _DataPools()


class PositionQuery(BaseModel):
    position_id: str  # 如 pos_35


class ListPositionsQuery(BaseModel):
    """无参数：一次返回全部标准岗位目录（id+分组+名称），避免逐个穷举。"""


class JdQuery(BaseModel):
    jd_id: str


class EventQuery(BaseModel):
    event_id: str


def build_tools() -> list[ToolSpec]:
    """四个只读查证工具；返回内容截断控制 agent 上下文成本。"""

    def lookup_position(position_id: str) -> str:
        POOLS.load()
        assert POOLS.positions is not None
        pos = POOLS.positions.get(position_id)
        if pos is None:
            return f"未找到岗位 {position_id}（有效范围 pos_01~pos_{len(POOLS.positions):02d}）"
        summary = (pos.get("summary") or "")[:400]
        return json.dumps(
            {
                "position_id": pos["position_id"],
                "group": pos.get("group"),
                "name": pos["name"],
                "summary": summary,
            },
            ensure_ascii=False,
        )

    def list_positions() -> str:
        POOLS.load()
        assert POOLS.positions is not None
        return "\n".join(
            f"{p['position_id']} {p.get('group')}/{p['name']}" for p in POOLS.positions.values()
        )

    def lookup_jd(jd_id: str) -> str:
        POOLS.load()
        assert POOLS.parsed is not None
        jd = POOLS.parsed.get(jd_id)
        if jd is None:
            return f"未找到 JD {jd_id}"
        return json.dumps(
            {
                "title": jd.get("title"),
                "is_ai_role": jd.get("is_ai_role"),
                "domain_reason": jd.get("domain_reason"),
                "responsibilities": (jd.get("responsibilities") or [])[:6],
                "skill_mentions": jd.get("skill_mentions") or [],
                "unresolved": (jd.get("unresolved") or [])[:10],
            },
            ensure_ascii=False,
        )

    def lookup_event(event_id: str) -> str:
        POOLS.load()
        assert POOLS.events is not None
        ev = POOLS.events.get(event_id)
        if ev is None:
            return f"未找到事件 {event_id}"
        return json.dumps(
            {
                "title": ev.get("title"),
                "summary": (ev.get("summary") or "")[:300],
                "event_type": ev.get("event_type"),
                "fact_grade": ev.get("fact_grade"),
                "entities": ev.get("entities") or [],
                "skill_mentions": ev.get("skill_mentions") or [],
                "published_at": ev.get("published_at"),
            },
            ensure_ascii=False,
        )

    return [
        ToolSpec(
            name="lookup_position",
            description="按 position_id 查标准岗位的名称、分组与职责说明",
            args_model=PositionQuery,
            func=lookup_position,
        ),
        ToolSpec(
            name="list_positions",
            # 供未来需要目录浏览的场景；role 层已内联目录，当前各层工具集不包含它
            description="一次列出全部 46 个标准岗位（id+分组+名称）",
            args_model=ListPositionsQuery,
            func=list_positions,
        ),
        ToolSpec(
            name="lookup_jd",
            description="按 jd_id 查 JD 解析详情：职责、技能提及、领域判定与理由",
            args_model=JdQuery,
            func=lookup_jd,
        ),
        ToolSpec(
            name="lookup_event",
            description="按 event_id 查日报事件完整记录：标题、摘要、类型、事实分级、技能提及",
            args_model=EventQuery,
            func=lookup_event,
        ),
    ]


# ---------------------------------------------------------------- case 构建


def _csv_rows(layer: str) -> list[dict[str, str]]:
    csv_name = next(csv for _, (lyr, csv) in LAYER_OF_PREFIX.items() if lyr == layer)
    path = SAMPLES / csv_name
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def _positions_catalog() -> str:
    """role 层内联的全部岗位目录（id+分组+名称），省一次 list_positions 往返。"""
    try:
        POOLS.load()
        assert POOLS.positions is not None
        return "\n".join(
            f"{p['position_id']} {p.get('group')}/{p['name']}" for p in POOLS.positions.values()
        )
    except Exception:  # noqa: BLE001 - 目录不可用时退化为提示用工具查证
        return ""


def case_summary(task_id: str, annotation: dict[str, Any]) -> str:
    """从冻结样本 CSV + 预标注构建 case 任务文本（agent 的首条 user 消息）。"""
    prefix = task_id.split("-")[1]
    layer, _ = LAYER_OF_PREFIX[prefix]
    idx = int(task_id.split("-")[2])
    row = _csv_rows(layer)[idx]

    if layer == "role":
        catalog = _positions_catalog()
        system_output = f"系统岗位id={row['系统岗位id']}（method={row['method']}）"
        question = (
            "该 JD 映射到此标准岗位是否正确？"
            "（岗位目录已附上；用 lookup_position 查证该岗位职责，lookup_jd 查 JD 详情）"
        )
    elif layer == "domain":
        catalog = ""
        system_output = f"系统判定 is_ai_role={row['系统判定']}，理由：{row['判定理由']}"
        question = "该 JD 是否为 AI 岗位？（此层无需岗位映射，直接基于 JD 职责与技能判定即可）"
    else:
        catalog = ""
        system_output = (
            f"事件类型={row['事件类型']}，事实分级={row['事实分级']}，技能提及={row['技能提及']}"
        )
        question = "该事件的抽取字段是否正确、无编造？（此层无需岗位映射）"

    pre = annotation["decision"]
    pre_reason = annotation.get("rationale") or ""
    catalog_block = f"\n全部标准岗位目录（position_id 分组/名称）：\n{catalog}\n" if catalog else ""
    return (
        f"复核评测 case {task_id}（层：{layer}）\n"
        f"职位/标题：{row.get('职位名') or row.get('标题')}\n"
        f"系统输出：{system_output}\n"
        f"AI 预标注判定：{pre}（理由：{pre_reason}）\n"
        f"问题：{question}\n"
        f"jd_id/event_id：{row.get('jd_id') or row.get('event_id')}\n"
        f"{catalog_block}"
        f"请先用工具查证，再独立给出你的判定。"
    )


# ---------------------------------------------------------------- 复核执行


async def audit_case(
    porter: AgentPorter,
    task_id: str,
    annotation: dict[str, Any],
    run_dir: Path,
    *,
    budget: TokenBudget | None = None,
) -> tuple[AuditVerdict | None, AgentResult]:
    """单 case agent 复核；返回 (verdict, run 结果)。verdict 为 None 表示 run 未产出有效判定。"""
    spec: PromptSpec = load_prompt("eval-audit")
    layer = LAYER_OF_PREFIX[task_id.split("-")[1]][0]
    allowed = LAYER_TOOLS[layer]
    tools = [t for t in build_tools() if t.name in allowed]
    result = await run_agent(
        porter=porter,
        spec=spec,
        tools=tools,
        task=case_summary(task_id, annotation),
        output_model=AuditVerdict,
        run_dir=run_dir,
        max_steps=6,
        budget=budget or TokenBudget(total_tokens=20000),
    )
    verdict = AuditVerdict.model_validate(result.output) if result.output else None
    return verdict, result


def find_disagreements(
    verdicts: list[AuditVerdict], annotations: dict[str, dict[str, Any]]
) -> list[Disagreement]:
    """agent 判定 != 预标注判定（含任一方 UNKNOWN）即为分歧。"""
    out: list[Disagreement] = []
    for v in verdicts:
        pre = annotations.get(v.task_id, {}).get("decision", "?")
        if v.agent_decision != pre:
            out.append(
                Disagreement(
                    task_id=v.task_id,
                    layer=v.layer,
                    prelabel_decision=pre,
                    agent_decision=v.agent_decision,
                    rationale=v.rationale,
                    error_type=v.error_type,
                )
            )
    return out
