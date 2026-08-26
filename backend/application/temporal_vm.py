"""Temporal / Skills / Tasks 三个 Use Case 的聚合 View Model。"""

from __future__ import annotations

import csv
import json
import os
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
    confidence: float = 0.0
    recent: float = 0.0
    prior: float = 0.0
    rule_version: int = 1


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
    forecast_valid_until: str = ""
    model_version: str = "temporal-v1"
    prompt_version: str = "report-event-v3"
    rule_version: int = 1
    evidence_ids: list[str] = Field(default_factory=list)


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
    if os.getenv("DATABASE_URL"):
        return _build_temporal_db(os.environ["DATABASE_URL"])
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
            BacktestRecordVM(
                as_of=r["as_of"],
                skill_id=r["skill_id"],
                predicted=r["predicted"],
                actual=r["actual"],
                hit=r["hit"],
                confidence=r.get("confidence", 0.0),
                recent=r.get("recent", 0.0),
                prior=r.get("prior", 0.0),
                rule_version=r.get("rule_version", 1),
            )
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
    latest = max((r.as_of for r in records), default="")
    forecasts = [
        ForecastVM(
            forecast_id=f"fct-{record.skill_id}-{record.as_of}",
            skill_id=record.skill_id,
            mode="backtest",
            as_of_date=record.as_of,
            horizon_days=30,
            predicted_direction=record.predicted,
            predicted_heat=record.recent,
            confidence=record.confidence,
            forecast_valid_until=latest,
            rule_version=record.rule_version,
        )
        for record in records
        if record.as_of == latest
    ]
    return TemporalVM(
        backtests=backtests,
        backtest_records=records,
        forecasts=forecasts,
        signals=_load_signals(),
        suggestions=suggestions,
    )


def _build_temporal_db(dsn: str) -> TemporalVM:
    """数据库事实主库模式：读取导入后的时间情报，不回退前端 fixture。"""
    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """SELECT run_id, metrics, status FROM pipeline_runs
               WHERE run_type = 'backtest' ORDER BY run_id"""
        )
        runs = list(cur.fetchall())
        cur.execute(
            """SELECT run_id, as_of_date, skill_id, predicted_direction, actual_direction, hit,
                      confidence, recent, prior, rule_version FROM backtest_records
               ORDER BY as_of_date DESC LIMIT 30"""
        )
        records = list(cur.fetchall())
        cur.execute(
            """SELECT forecast_id, skill_id, as_of_date, horizon_days, predicted_direction,
                      predicted_heat, confidence, valid_until, rule_version, evidence_ids
               FROM forecasts ORDER BY as_of_date DESC"""
        )
        forecasts = list(cur.fetchall())
        cur.execute(
            """SELECT signal_id, item_id, skill_id, signal_type, observed_at, confidence,
                      evidence_ids, payload FROM trend_signals
               ORDER BY observed_at DESC LIMIT 500"""
        )
        signals = list(cur.fetchall())
        cur.execute(
            """SELECT suggestion_id, job_id, skill_id, change_type, reason, review_status
               FROM job_impact_suggestions ORDER BY suggestion_id"""
        )
        suggestions = list(cur.fetchall())
    return TemporalVM(
        backtests=[
            BacktestRunVM(
                run_id=row["run_id"],
                as_of_date=(row["metrics"].get("as_of_points") or [""])[0],
                horizon_days=int(row["run_id"].removeprefix("bt-h")),
                status=row["status"],
                metrics=row["metrics"],
            )
            for row in runs
        ],
        backtest_records=[
            BacktestRecordVM(
                as_of=row["as_of_date"].isoformat(),
                skill_id=row["skill_id"],
                predicted=row["predicted_direction"],
                actual=row["actual_direction"],
                hit=row["hit"],
                confidence=row["confidence"],
                recent=row["recent"],
                prior=row["prior"],
                rule_version=row["rule_version"],
            )
            for row in records
        ],
        forecasts=[
            ForecastVM(
                forecast_id=row["forecast_id"],
                skill_id=row["skill_id"],
                as_of_date=row["as_of_date"].isoformat(),
                horizon_days=row["horizon_days"],
                predicted_direction=row["predicted_direction"],
                predicted_heat=row["predicted_heat"],
                confidence=row["confidence"],
                forecast_valid_until=row["valid_until"].isoformat() if row["valid_until"] else "",
                rule_version=row["rule_version"],
                evidence_ids=row["evidence_ids"],
            )
            for row in forecasts
        ],
        signals=[
            TrendSignalVM(
                signal_id=row["signal_id"],
                item_id=row["item_id"],
                canonical_skill_id=row["skill_id"],
                signal_type=row["signal_type"],
                observed_at=row["observed_at"].isoformat(),
                evidence_span=row["payload"].get("evidence_span", ""),
                confidence=row["confidence"],
                evidence_ids=row["evidence_ids"],
            )
            for row in signals
        ],
        suggestions=[
            SuggestionVM(
                suggestion_id=row["suggestion_id"],
                job_id=row["job_id"],
                skill_id=row["skill_id"],
                change_type=row["change_type"],
                reason=row["reason"],
                review_status=row["review_status"],
            )
            for row in suggestions
        ],
    )


def _load_signals(limit: int = 500) -> list[TrendSignalVM]:
    """读 sigbuild 产物：近 90 天提及级 TrendSignal（最新优先，截断防 VM 过大）。"""
    from datetime import UTC, datetime, timedelta

    p = P / "temporal" / "signals.jsonl"
    if not p.is_file():
        return []
    cutoff = (datetime.now(UTC) - timedelta(days=90)).isoformat()
    rows = []
    for line in p.open(encoding="utf-8"):
        s = json.loads(line)
        if s.get("observed_at", "") >= cutoff:
            rows.append(TrendSignalVM(**s))
    return rows[:limit]


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
    # 关联岗位版本（published 扫描聚合）与市场信号基础档（JD 提及）
    job_versions: list[dict] = Field(default_factory=list)
    signal: dict = Field(default_factory=dict)
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
    "cap_01": "LLM",
    "cap_02": "LLM",
    "cap_03": "LLM",
    "cap_04": "Agent",
    "cap_05": "多模态",
    "cap_06": "RAG",
    "cap_07": "数据",
    "cap_08": "数据",
    "cap_09": "数据",
    "cap_10": "数据",
    "cap_11": "数据",
    "cap_12": "工程",
    "cap_13": "工程",
    "cap_14": "工程",
    "cap_15": "工程",
    "cap_16": "工程",
    "cap_17": "工程",
    "cap_18": "工程",
    "cap_19": "治理",
    "cap_20": "治理",
    "cap_21": "工程",
    "cap_22": "工程",
    "cap_23": "工程",
    "cap_24": "工程",
    "cap_25": "工程",
    "cap_26": "工程",
    "cap_27": "工程",
    "cap_28": "工程",
    "cap_29": "工程",
    "cap_30": "治理",
}


def _job_versions_index() -> dict[str, list[dict]]:
    """skill_id -> 关联岗位版本列表（扫全部 published，按权重降序）。"""
    index: dict[str, list[dict]] = {}
    pub_dir = P / "jobversions" / "published"
    for p in sorted(pub_dir.glob("*.json")) if pub_dir.is_dir() else []:
        job = json.loads(p.read_text(encoding="utf-8"))
        for role, key in (
            ("required", "required_skill_ids"),
            ("preferred", "preferred_skill_ids"),
        ):
            for s in job.get(key, []):
                sid = s.get("skill_id", "")
                if sid:
                    index.setdefault(sid, []).append(
                        {
                            "version_id": job.get("version_id", p.stem),
                            "title": job.get("title", ""),
                            "role": role,
                            "weight": s.get("weight"),
                        }
                    )
    for refs in index.values():
        refs.sort(key=lambda x: -(x["weight"] or 0))
    return index


def _mention_counts() -> tuple[dict[str, int], dict[str, int], int]:
    """(能力域提及数, 技能点提及数, 总提及数)，源自 jd-parsed resolved。"""
    caps: dict[str, int] = {}
    points: dict[str, int] = {}
    total = 0
    parsed = P / "jd-opencli" / "jd-parsed.jsonl"
    if not parsed.is_file():
        return caps, points, total
    for line in parsed.open(encoding="utf-8"):
        for x in json.loads(line).get("resolved") or []:
            sid = x.get("skill_id", "")
            if sid:
                caps[sid] = caps.get(sid, 0) + 1
                total += 1
            pid = x.get("point_id")
            if pid:
                points[pid] = points.get(pid, 0) + 1
    return caps, points, total


def build_skill_graph(job_version_id: str = "ai-agent-v2") -> SkillGraphVM:
    """从 published 版本 + SKILLS 词典构建技能图谱。"""
    jobs_idx = _job_versions_index()
    cap_counts, point_counts, mention_total = _mention_counts()

    def _signal(counts: dict[str, int], key: str) -> dict:
        n = counts.get(key, 0)
        return {
            "jd_mentions": n,
            "mention_share": round(n / mention_total, 3) if mention_total else 0,
        }

    job = {}
    p = P / "jobversions" / "published" / f"{job_version_id}.json"
    if p.is_file():
        job = json.loads(p.read_text(encoding="utf-8"))
    required = {s["skill_id"] for s in job.get("required_skill_ids", [])}
    preferred = {s["skill_id"] for s in job.get("preferred_skill_ids", [])}

    nodes, edges = [], []
    # 根节点（岗位）
    nodes.append(
        SkillNodeVM(
            id="root",
            label=job.get("title", job_version_id),
            capability_id="root",
            role="required",
            status="added",
            position={"x": 400, "y": 40},
            tech_stack="LLM",
        )
    )
    caps_file = P / "capability-matrix" / "capabilities.json"
    if caps_file.is_file():
        caps = json.loads(caps_file.read_text(encoding="utf-8"))["capabilities"]
        for i, c in enumerate(caps):
            sid = c["capability_id"]
            is_req = sid in required
            is_pref = sid in preferred
            if not (is_req or is_pref):
                continue
            nodes.append(
                SkillNodeVM(
                    id=sid,
                    label=c["name"],
                    capability_id=sid,
                    role="required" if is_req else "preferred",
                    status="added" if is_req else "stable",
                    aliases=c.get("aliases", [])[:3],
                    position={"x": 400 + 280 * (1 if i % 2 else -1), "y": 140 + (i // 2) * 90},
                    tech_stack=_TECH_MAP.get(sid, "工程"),
                    job_versions=jobs_idx.get(sid, []),
                    signal=_signal(cap_counts, sid),
                )
            )
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
            for j, point in enumerate(entry.get("points", [])):
                pt = point.get("name", "") if isinstance(point, dict) else point[0]
                if not pt:
                    continue
                pid = f"{cap}.{pt}"
                nodes.append(
                    SkillNodeVM(
                        id=pid,
                        label=pt,
                        capability_id=cap,
                        point_name=pt,
                        role="preferred",
                        status="stable",
                        position={
                            "x": 400 + (j % 3 - 1) * 120 + (280 if cap in required else -280),
                            "y": 400 + j * 60,
                        },
                        tech_stack=_TECH_MAP.get(cap, "工程"),
                        job_versions=jobs_idx.get(pid, []),
                        signal=_signal(point_counts, pid),
                    )
                )
                edges.append(SkillEdgeVM(id=f"e-{cap}-{pid}", source=cap, target=pid))

    return SkillGraphVM(
        run={"id": "skill-graph-v1", "datasetVersion": "v6", "status": "REVIEWING"},
        context={
            "jobTitle": job.get("title", ""),
            "baselineVersion": "v1",
            "targetVersion": job_version_id,
            "timeWindow": job.get("valid_from", ""),
        },
        nodes=nodes,
        edges=edges,
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
            tasks.append(
                ReviewTaskVM(
                    task_id=f"task-{task_type}-{i:03d}",
                    task_type=task_type,
                    source_record_id=r.get("jd_id", r.get("event_id", "")),
                    status=status,
                    priority="high" if i < 10 else "medium",
                    system_output={
                        "title": r.get("职位名", r.get("标题", "")),
                        "verdict_col": done_col,
                    },
                )
            )
    return TaskListVM(
        tasks=tasks, total=len(tasks), pending=sum(1 for t in tasks if t.status == "PENDING")
    )
