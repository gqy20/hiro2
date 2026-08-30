"""Temporal / Skills / Tasks 三个 Use Case 的聚合 View Model。"""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .annotate import DATASET_VERSION
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
    evidence_ids: list[str] = Field(default_factory=list)


class TemporalVM(_VM):
    backtests: list[BacktestRunVM]
    backtest_records: list[BacktestRecordVM]
    forecasts: list[ForecastVM]
    signals: list[TrendSignalVM]
    suggestions: list[SuggestionVM]


class TemporalSignalListVM(_VM):
    signals: list[TrendSignalVM]
    total: int
    earliest_observed_at: str = ""
    latest_observed_at: str = ""


def build_temporal() -> TemporalVM:
    """从 backtest / leadtime / changeset 产物聚合 temporal 视图。"""
    if os.getenv("DATABASE_URL"):
        vm = _build_temporal_db(os.environ["DATABASE_URL"])
        merged = _apply_suggestion_reviews(vm.suggestions)
        return TemporalVM(**{**vm.model_dump(), "suggestions": merged})
    backtests: list[BacktestRunVM] = []
    records: list[BacktestRecordVM] = []
    for h in (30, 60, 90):
        # 双规则版本读取：v1 为历史基线，v2（存在时）为当前生产规则
        for rule, suffix in ((1, ""), (2, "-r2")):
            p = P / "wechat-mp" / f"backtest-h{h}{suffix}.json"
            if not p.is_file():
                continue
            d = json.loads(p.read_text(encoding="utf-8"))
            m = d["metrics"]
            backtests.append(
                BacktestRunVM(
                    run_id=f"bt-h{h}{'-r2' if rule == 2 else ''}",
                    as_of_date=m["as_of_points"][0] if m["as_of_points"] else "",
                    horizon_days=h,
                    status="SUCCEEDED",
                    metrics={
                        "predictions": m["predictions"],
                        "hits": m["hits"],
                        "accuracy": m["accuracy"],
                        "flat_baseline_accuracy": m["flat_baseline_accuracy"],
                        "rule_version": m.get("rule_version", rule),
                        "error_types": m.get("error_types", {}),
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
                    rule_version=r.get("rule_version", rule),
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
    # 当前预测只取最新规则版本的记录（历史规则仅作复盘对比）
    current_rule = max((r.rule_version for r in records), default=1)
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
            model_version=f"temporal-r{record.rule_version}",
            rule_version=record.rule_version,
        )
        for record in records
        if record.as_of == latest and record.rule_version == current_rule
    ]
    return TemporalVM(
        backtests=backtests,
        backtest_records=records,
        forecasts=forecasts,
        signals=_load_signals(),
        suggestions=_apply_suggestion_reviews(suggestions),
    )


def build_temporal_signals() -> TemporalSignalListVM:
    """返回完整信号流，由前端按时间范围筛选并渐进渲染。"""
    dsn = os.getenv("DATABASE_URL")
    signals = _load_all_signals_db(dsn) if dsn else _load_signals(None, None)
    observed = [signal.observed_at for signal in signals if signal.observed_at]
    return TemporalSignalListVM(
        signals=signals,
        total=len(signals),
        earliest_observed_at=min(observed, default=""),
        latest_observed_at=max(observed, default=""),
    )


def _load_all_signals_db(dsn: str) -> list[TrendSignalVM]:
    import psycopg

    with psycopg.connect(dsn) as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        cur.execute(
            """SELECT signal_id, item_id, skill_id, signal_type, observed_at, confidence,
                      evidence_ids, payload FROM trend_signals
               ORDER BY observed_at DESC"""
        )
        rows = list(cur.fetchall())
    return [
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
        for row in rows
    ]


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
               ORDER BY observed_at DESC LIMIT 2000"""
        )
        signals = list(cur.fetchall())
        cur.execute(
            """SELECT s.suggestion_id, s.job_id, s.skill_id, s.change_type, s.reason,
                      s.review_status, COALESCE(f.evidence_ids, '{}') AS evidence_ids
               FROM job_impact_suggestions s
               LEFT JOIN forecasts f ON f.forecast_id = s.forecast_id
               ORDER BY s.suggestion_id"""
        )
        suggestions = list(cur.fetchall())
    return TemporalVM(
        backtests=[
            BacktestRunVM(
                run_id=row["run_id"],
                as_of_date=(row["metrics"].get("as_of_points") or [""])[0],
                # run_id 形如 bt-h30 / bt-h30-r2，horizon 取数字段
                horizon_days=int(row["run_id"].removeprefix("bt-h").split("-")[0]),
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
                evidence_ids=list(row.get("evidence_ids") or []),
            )
            for row in suggestions
        ],
    )


def _load_suggestion_reviews() -> dict[str, dict]:
    """读取建议审核动作：review-actions.jsonl 中 sug- 前缀目标的最新一条。

    审核记录为 append-only（与岗位审核同一份事实日志），此处只取终态。
    """
    path = ROOT / "data" / "processed" / "review" / "review-actions.jsonl"
    latest: dict[str, dict] = {}
    if not path.is_file():
        return latest
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        tid = rec.get("target_id", "")
        if tid.startswith("sug-"):
            latest[tid] = rec
    return latest


_DECISION_TO_STATUS = {
    "accepted": "ACCEPTED",
    "rejected": "REJECTED",
    "modified": "MODIFIED",
    "needs_evidence": "PENDING",
}


def _apply_suggestion_reviews(suggestions: list[SuggestionVM]) -> list[SuggestionVM]:
    """把审核动作合并到建议 VM（状态 + 修改后的建议级别）。"""
    reviews = _load_suggestion_reviews()
    merged: list[SuggestionVM] = []
    for s in suggestions:
        rec = reviews.get(s.suggestion_id)
        if rec is None:
            merged.append(s)
            continue
        data = s.model_dump()
        data["review_status"] = _DECISION_TO_STATUS.get(rec["decision"], "PENDING")
        if rec.get("suggested_level"):
            data["suggested_level"] = rec["suggested_level"]
        merged.append(SuggestionVM(**data))
    return merged


def _load_signals(limit: int | None = 2000, since_days: int | None = 90) -> list[TrendSignalVM]:
    """读 sigbuild 产物；聚合接口保留近 90 天上限，信号流可读取完整历史。"""
    from datetime import UTC, datetime, timedelta

    p = P / "temporal" / "signals.jsonl"
    if not p.is_file():
        return []
    cutoff = (
        (datetime.now(UTC) - timedelta(days=since_days)).isoformat()
        if since_days is not None
        else None
    )
    rows_by_id: dict[str, TrendSignalVM] = {}
    for line in p.open(encoding="utf-8"):
        s = json.loads(line)
        if cutoff is None or s.get("observed_at", "") >= cutoff:
            rows_by_id[str(s["signal_id"])] = TrendSignalVM(**s)
    rows = list(rows_by_id.values())
    rows.sort(key=lambda signal: signal.observed_at, reverse=True)
    return rows if limit is None else rows[:limit]


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

    p = P / "jobversions" / "published" / f"{job_version_id}.json"
    if not p.is_file():
        raise FileNotFoundError(f"岗位版本不存在: {job_version_id}")
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
    run_id: str = "eval-v3"
    dataset_version: str = DATASET_VERSION
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
    """从 evaluation/samples 生成 ReviewTask 列表，合并标注状态与 AI 预标注建议。"""
    from .annotate import load_annotations, load_prelabels

    annotations = load_annotations()
    prelabels = load_prelabels()
    tasks: list[ReviewTaskVM] = []
    samples_dir = ROOT / "evaluation" / "samples"
    position_names: dict[str, str] = {}
    position_path = P / "capability-matrix" / "positions.jsonl"
    if position_path.is_file():
        for line in position_path.open(encoding="utf-8"):
            if not line.strip():
                continue
            position = json.loads(line)
            position_names[str(position.get("position_id", ""))] = str(position.get("name", ""))
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
            task_id = f"task-{task_type}-{i:03d}"
            ann = annotations.get(task_id)
            resolved = bool(r.get(done_col, "").strip()) or ann is not None
            title = r.get("职位名", r.get("标题", ""))
            if task_type == "role_level":
                predicted_id = r.get("系统岗位id", "")
                output = {
                    "title": title,
                    "question": "系统岗位映射是否准确？",
                    "predicted_position": position_names.get(predicted_id, predicted_id),
                    "mapping_method": r.get("method", ""),
                }
            elif task_type == "evidence_audit":
                output = {
                    "title": title,
                    "question": "系统的岗位领域判断是否准确？",
                    "domain_judgment": r.get("系统判定", ""),
                    "judgment_reason": r.get("判定理由", ""),
                }
            else:
                output = {
                    "title": title,
                    "question": "事件类型、事实等级和技能提及是否准确？",
                    "event_date": r.get("日期", ""),
                    "event_type": r.get("事件类型", ""),
                    "fact_grade": r.get("事实分级", ""),
                    "skill_mentions": r.get("技能提及", ""),
                }
            if ann:
                output["last_decision"] = ann["decision"]
                output["last_rationale"] = ann.get("rationale", "")
            pre = prelabels.get(task_id)
            if pre and not ann:
                output["prelabel"] = {
                    "suggested_decision": pre["suggested_decision"],
                    "confidence": pre["confidence"],
                    "rationale": pre["rationale"],
                    "corrected_payload": pre.get("corrected_payload"),
                }
            tasks.append(
                ReviewTaskVM(
                    task_id=task_id,
                    task_type=task_type,
                    source_record_id=r.get("jd_id", r.get("event_id", "")),
                    status="RESOLVED" if resolved else "PENDING",
                    priority="high" if i < 10 else "medium",
                    system_output=output,
                )
            )
    return TaskListVM(
        tasks=tasks, total=len(tasks), pending=sum(1 for t in tasks if t.status == "PENDING")
    )
