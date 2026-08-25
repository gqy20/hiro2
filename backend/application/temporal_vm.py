"""Temporal / Skills / Tasks 三个 Use Case 的聚合 View Model。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .repos import P

ROOT = Path(__file__).resolve().parents[2]


class _VM(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ============================================================ temporal


class BacktestRunVM(_VM):
    run_id: str
    as_of_date: str
    horizon_days: int
    status: str
    metrics: dict


class BacktestRecordVM(_VM):
    as_of: str
    skill_id: str
    predicted: str
    actual: str
    hit: bool


class TrendSignalVM(_VM):
    signal_id: str
    item_id: str
    entity_type: str = "skill"
    canonical_skill_id: str
    signal_type: str = "mention"
    observed_at: str
    evidence_span: str = ""
    confidence: float = 0.6
    evidence_ids: list[str] = Field(default_factory=list)


class ForecastVM(_VM):
    forecast_id: str
    skill_id: str
    mode: str = "backtest"
    as_of_date: str
    horizon_days: int
    current_phase: str = "stable"
    predicted_direction: str = "flat"
    predicted_heat: float = 0.0
    confidence: float = 0.4


class SuggestionVM(_VM):
    suggestion_id: str
    forecast_id: str = ""
    job_id: str = "job_ai_agent"
    skill_id: str
    change_type: str = "add"
    suggested_level: str = ""
    reason: str
    review_status: str = "PENDING"


class TemporalVM(_VM):
    backtests: list[BacktestRunVM]
    backtest_records: list[BacktestRecordVM]
    forecasts: list[ForecastVM]
    signals: list[TrendSignalVM]
    suggestions: list[SuggestionVM]


def build_temporal() -> TemporalVM:
    """从 backtest / leadtime / changeset 产物聚合 temporal 视图。"""
    backtests: list[BacktestRunVM] = []
    records: list[BacktestRecordVM] = []
    for h in (30, 60, 90):
        p = P / "wechat-mp" / f"backtest-h{h}.json"
        if not p.is_file():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        m = d["metrics"]
        backtests.append(
            BacktestRunVM(
                run_id=f"bt-h{h}",
                as_of_date=m["as_of_points"][0] if m["as_of_points"] else "",
                horizon_days=h,
                status="SUCCEEDED",
                metrics={
                    "predictions": m["predictions"],
                    "hits": m["hits"],
                    "accuracy": m["accuracy"],
                    "baseline": m["flat_baseline_accuracy"],
                },
            )
        )
        records.extend(
            BacktestRecordVM(as_of=r["as_of"], skill_id=r["skill_id"], predicted=r["predicted"],
                             actual=r["actual"], hit=r["hit"])
            for r in d["records"][:30]  # 截断防过大
        )

    # leadtime 转为 suggestions
    suggestions: list[SuggestionVM] = []
    lt_path = P / "wechat-mp" / "leadtime.json"
    if lt_path.is_file():
        lt = json.loads(lt_path.read_text(encoding="utf-8"))
        for r in lt.get("rows", []):
            suggestions.append(
                SuggestionVM(
                    suggestion_id=f"sug-{r['capability_id']}",
                    skill_id=r["capability_id"],
                    change_type="promote" if r["lead_days"] > 200 else "add",
                    reason=f"{r['name']}：信号领先 {r['lead_days']} 天（{r['reliability']}）",
                )
            )
    return TemporalVM(
        backtests=backtests,
        backtest_records=records,
        forecasts=[],
        signals=[],
        suggestions=suggestions,
    )


# ============================================================ skills graph


class SkillNodeVM(_VM):
    id: str
    label: str
    capability_id: str
    point_name: str | None = None
    role: str = "required"
    status: str = "stable"
    aliases: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    position: dict = Field(default_factory=dict)
    tech_stack: str = "LLM"


class SkillEdgeVM(_VM):
    id: str
    source: str
    target: str


class SkillGraphVM(_VM):
    fixture_version: str = "v2"
    mode: str = "real"
    run: dict = Field(default_factory=dict)
    context: dict = Field(default_factory=dict)
    nodes: list[SkillNodeVM]
    edges: list[SkillEdgeVM]
    filter_options: dict = Field(default_factory=dict)


_TECH_MAP = {
    "cap_01": "LLM", "cap_02": "LLM", "cap_03": "LLM", "cap_04": "Agent",
    "cap_05": "多模态", "cap_06": "RAG", "cap_07": "数据", "cap_08": "数据",
    "cap_09": "数据", "cap_10": "数据", "cap_11": "数据", "cap_12": "工程",
    "cap_13": "工程", "cap_14": "工程", "cap_15": "工程", "cap_16": "工程",
    "cap_17": "工程", "cap_18": "工程", "cap_19": "治理", "cap_20": "治理",
    "cap_21": "工程", "cap_22": "工程", "cap_23": "工程", "cap_24": "工程",
    "cap_25": "工程", "cap_26": "工程", "cap_27": "工程", "cap_28": "工程",
    "cap_29": "工程", "cap_30": "治理",
}


def build_skill_graph(job_version_id: str = "ai-agent-v2") -> SkillGraphVM:
    """从 published 版本 + SKILLS 词典构建技能图谱。"""
    job = {}
    p = P / "jobversions" / "published" / f"{job_version_id}.json"
    if p.is_file():
        job = json.loads(p.read_text(encoding="utf-8"))
    required = {s["skill_id"] for s in job.get("required_skill_ids", [])}
    preferred = {s["skill_id"] for s in job.get("preferred_skill_ids", [])}

    nodes, edges = [], []
    # 根节点（岗位）
    nodes.append(SkillNodeVM(
        id="root", label=job.get("title", job_version_id), capability_id="root",
        role="required", status="added", position={"x": 400, "y": 40}, tech_stack="LLM",
    ))
    caps_file = P / "capability-matrix" / "capabilities.json"
    if caps_file.is_file():
        caps = json.loads(caps_file.read_text(encoding="utf-8"))["capabilities"]
        for i, c in enumerate(caps):
            sid = c["capability_id"]
            is_req = sid in required
            is_pref = sid in preferred
            if not (is_req or is_pref):
                continue
            nodes.append(SkillNodeVM(
                id=sid, label=c["name"], capability_id=sid,
                role="required" if is_req else "preferred",
                status="added" if is_req else "stable",
                aliases=c.get("aliases", [])[:3],
                position={"x": 400 + 280 * (1 if i % 2 else -1), "y": 140 + (i // 2) * 90},
                tech_stack=_TECH_MAP.get(sid, "工程"),
            ))
            edges.append(SkillEdgeVM(id=f"e-root-{sid}", source="root", target=sid))
    # 技能点
    skills_yml = ROOT / "data" / "SKILLS.yml"
    if skills_yml.is_file():
        import yaml

        d = yaml.safe_load(skills_yml.read_text(encoding="utf-8"))
        for entry in d.get("entries", []):
            cap = entry["capability_id"]
            if cap not in required and cap not in preferred:
                continue
            for j, (pt, _) in enumerate(entry.get("points", [])):
                pid = f"{cap}.{pt}"
                nodes.append(SkillNodeVM(
                    id=pid, label=pt, capability_id=cap, point_name=pt,
                    role="preferred", status="stable",
                    position={"x": 400 + (j % 3 - 1) * 120 + (280 if cap in required else -280),
                              "y": 400 + j * 60},
                    tech_stack=_TECH_MAP.get(cap, "工程"),
                ))
                edges.append(SkillEdgeVM(id=f"e-{cap}-{pid}", source=cap, target=pid))

    return SkillGraphVM(
        run={"id": "skill-graph-v1", "datasetVersion": "v6", "status": "REVIEWING"},
        context={"jobTitle": job.get("title", ""), "baselineVersion": "v1",
                 "targetVersion": job_version_id, "timeWindow": job.get("valid_from", "")},
        nodes=nodes, edges=edges,
        filter_options={
            "techStacks": list(set(_TECH_MAP.values())),
            "roles": ["required", "preferred"],
            "capabilityTypes": ["capability", "point"],
        },
    )


# ============================================================ tasks


class ReviewTaskVM(_VM):
    task_id: str
    task_type: str
    source_record_id: str
    run_id: str = "eval-v1"
    dataset_version: str = "eval-v1-20260825"
    priority: str = "medium"
    assignee_id: str = ""
    status: str = "PENDING"
    system_output: dict = Field(default_factory=dict)
    evidence_ids: list[str] = Field(default_factory=list)


class TaskListVM(_VM):
    tasks: list[ReviewTaskVM]
    total: int
    pending: int


def build_tasks() -> TaskListVM:
    """从 evaluation/samples 生成 ReviewTask 列表。"""
    tasks: list[ReviewTaskVM] = []
    samples_dir = ROOT / "evaluation" / "samples"
    for csv_name, task_type in [
        ("role-mapping.csv", "role_level"),
        ("domain-judgment.csv", "evidence_audit"),
        ("event-extraction.csv", "skill_mapping"),
    ]:
        p = samples_dir / csv_name
        if not p.is_file():
            continue
        rows = list(csv.DictReader(p.open(encoding="utf-8-sig")))
        for i, r in enumerate(rows):
            done_col = next((c for c in r if "?" in c), "")
            status = "RESOLVED" if r.get(done_col, "").strip() else "PENDING"
            tasks.append(ReviewTaskVM(
                task_id=f"task-{task_type}-{i:03d}",
                task_type=task_type,
                source_record_id=r.get("jd_id", r.get("event_id", "")),
                status=status,
                priority="high" if i < 10 else "medium",
                system_output={"title": r.get("职位名", r.get("标题", "")),
                               "verdict_col": done_col},
            ))
    return TaskListVM(tasks=tasks, total=len(tasks),
                      pending=sum(1 for t in tasks if t.status == "PENDING"))
