"""数据资产目录 View Model，聚合 manifest 与处理产物供内部治理界面使用。"""

from __future__ import annotations

import functools
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]


class DatasetSource(BaseModel):
    """单个来源通道（来自 data/SOURCES.yml 的 D0 登记）。"""

    id: str
    type: str = ""
    time_range: list[str] = Field(default_factory=list)
    ingestion_mode: str = ""
    license: str = ""
    notes: str = ""


class DatasetItem(BaseModel):
    id: str
    name: str
    category: str
    records: int = 0
    valid_records: int = 0
    version: str = ""
    status: str = "可用"
    formats: list[str] = Field(default_factory=list)
    source: str = ""
    updated_at: str = ""
    quality: int = 0
    sources: list[DatasetSource] = Field(default_factory=list)


class DatasetOverview(BaseModel):
    total_datasets: int = 0
    total_records: int = 0
    ready_datasets: int = 0
    pending_records: int = 0
    datasets: list[DatasetItem] = Field(default_factory=list)


class DatasetVersion(BaseModel):
    dataset_id: str
    version: str
    status: str
    records: int
    valid_records: int
    pending_records: int
    quality: int
    manifest_hash: str = ""
    manifest: dict = Field(default_factory=dict)
    run_id: str = ""
    imported_at: str = ""


class DatasetDetail(BaseModel):
    dataset: DatasetItem
    versions: list[DatasetVersion] = Field(default_factory=list)


class DatasetSourceStats(BaseModel):
    evidence_count: int = 0
    reviewed_evidence_count: int | None = None
    average_quality: float | None = None
    latest_evidence_at: str = ""
    claim_types: dict[str, int] = Field(default_factory=dict)
    attribution: str = "exact"
    attribution_note: str = ""


class DatasetSourceDetail(BaseModel):
    dataset_id: str
    dataset_version: str
    source: DatasetSource
    stats: DatasetSourceStats


# 数据集 -> SOURCES.yml 登记的来源通道。派生（evidence）、受控（resumes）、
# 冻结评测集（evaluation）无外部来源登记，留空由前端展示派生说明。
DATASET_SOURCES: dict[str, list[str]] = {
    "jd": ["jd-corp", "jd-opencli", "jd-51job-har", "jd-boss", "jd-archive"],
    "temporal": ["wechat-mp", "feeds", "arxiv", "pypi-pkgstats"],
    "capability": ["capability-matrix", "standards", "onet-history", "policy"],
}

DATASET_MANIFESTS: dict[str, Path] = {
    "jd": ROOT / "data" / "processed" / "jd-opencli" / "manifest.json",
    "temporal": ROOT / "data" / "processed" / "wechat-mp" / "manifest.json",
    "capability": ROOT / "data" / "processed" / "capability-matrix" / "manifest.json",
    "evidence": ROOT / "data" / "processed" / "evidence" / "manifest.json",
    "evaluation": ROOT / "evaluation" / "samples" / "manifest.json",
}


@functools.lru_cache(maxsize=1)
def _source_registry() -> dict[str, DatasetSource]:
    """读取 data/SOURCES.yml（D0 来源登记），失败时返回空表。"""
    path = ROOT / "data" / "SOURCES.yml"
    if not path.is_file():
        return {}
    try:
        payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return {}
    registry: dict[str, DatasetSource] = {}
    for raw in (payload or {}).get("sources", []):
        if not isinstance(raw, dict) or not raw.get("id"):
            continue
        time_range = [str(v) for v in raw.get("time_range") or []]
        registry[str(raw["id"])] = DatasetSource(
            id=str(raw["id"]),
            type=str(raw.get("type", "")),
            time_range=time_range,
            ingestion_mode=str(raw.get("ingestion_mode", "")),
            license=str(raw.get("license", "")).strip(),
            notes=str(raw.get("notes", "")).strip(),
        )
    return registry


def _attach_sources(items: list[DatasetItem]) -> None:
    registry = _source_registry()
    for item in items:
        item.sources = [
            registry[sid] for sid in DATASET_SOURCES.get(item.id, []) if sid in registry
        ]


def _line_count(path: Path) -> int:
    if not path.is_file():
        return 0
    return sum(1 for line in path.open(encoding="utf-8", errors="ignore") if line.strip())


def _manifest_version(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(
        payload.get("dataset_version") or payload.get("version") or payload.get("batch") or ""
    )


def _manifest_summary(path: Path) -> tuple[dict, str, str]:
    if not path.is_file():
        return {}, "", ""
    raw = path.read_bytes()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}, hashlib.sha256(raw).hexdigest(), ""
    summary = {
        key: payload[key]
        for key in (
            "source_id",
            "source_type",
            "ingestion_mode",
            "file_count",
            "total_bytes",
            "dataset_version",
            "version",
            "seed",
        )
        if key in payload
    }
    if "files" in payload:
        summary["file_count"] = len(payload["files"])
    imported_at = datetime.fromtimestamp(path.stat().st_mtime, UTC).isoformat()
    return summary, hashlib.sha256(raw).hexdigest(), imported_at


def _item(
    dataset_id: str,
    name: str,
    category: str,
    records: int,
    version: str,
    formats: list[str],
    source: str,
    quality: int,
    status: str = "可用",
) -> DatasetItem:
    return DatasetItem(
        id=dataset_id,
        name=name,
        category=category,
        records=records,
        valid_records=records,
        version=version,
        status=status,
        formats=formats,
        source=source,
        quality=quality,
    )


def build_dataset_overview() -> DatasetOverview:
    processed = ROOT / "data" / "processed"
    evaluation = ROOT / "evaluation" / "samples"
    items = [
        _item(
            "jd",
            "招聘岗位",
            "业务数据",
            _line_count(processed / "jd-opencli" / "norm-jd.jsonl"),
            _manifest_version(processed / "jd-opencli" / "manifest.json") or "jd-v3",
            ["JSONL", "CSV"],
            "企业招聘站、招聘平台",
            94,
        ),
        _item(
            "temporal",
            "时间情报",
            "事件数据",
            _line_count(processed / "wechat-mp" / "events.jsonl"),
            _manifest_version(processed / "wechat-mp" / "manifest.json") or "temporal-v2",
            ["JSONL"],
            "日报与 RSS 来源",
            91,
        ),
        _item(
            "capability",
            "能力标准",
            "主数据",
            _line_count(processed / "capability-matrix" / "position-skills.jsonl"),
            _manifest_version(processed / "capability-matrix" / "manifest.json") or "skill-v6",
            ["JSON", "JSONL", "YAML"],
            "职业标准与能力矩阵",
            98,
            "已审核",
        ),
        _item(
            "evidence",
            "证据记录",
            "分析数据",
            _line_count(processed / "evidence" / "evidence.jsonl"),
            "evidence-v2",
            ["JSONL"],
            "岗位、日报与标准数据",
            96,
        ),
        _item(
            "resumes",
            "简历档案",
            "候选人数据",
            _line_count(processed / "candidates" / "resume-archive.jsonl"),
            "resume-v2",
            ["PDF", "DOCX", "JSONL"],
            "候选人上传与受控导入",
            67,
            "部分解析",
        ),
        _item(
            "evaluation",
            "评测样本",
            "评测集",
            sum(
                _line_count(evaluation / name) - 1
                for name in ("role-mapping.csv", "domain-judgment.csv", "event-extraction.csv")
            ),
            _manifest_version(evaluation / "manifest.json") or "eval-v1",
            ["CSV", "JSON"],
            "冻结标注集",
            100,
            "已冻结",
        ),
    ]
    resume_item = next((item for item in items if item.id == "resumes"), None)
    if resume_item:
        archive_rows = []
        archive_path = processed / "candidates" / "resume-archive.jsonl"
        if archive_path.is_file():
            archive_rows = [
                json.loads(line) for line in archive_path.open(encoding="utf-8") if line.strip()
            ]
        latest_rows = {
            str(row.get("resume_id")): row for row in archive_rows if row.get("resume_id")
        }
        parsed = sum(bool(row.get("profile")) for row in latest_rows.values())
        items[items.index(resume_item)] = resume_item.model_copy(
            update={"records": len(latest_rows), "valid_records": parsed}
        )
    total = sum(item.records for item in items)
    ready = sum(item.status in {"可用", "已审核", "已冻结"} for item in items)
    pending = sum(item.records - item.valid_records for item in items)
    _attach_sources(items)
    return DatasetOverview(
        total_datasets=len(items),
        total_records=total,
        ready_datasets=ready,
        pending_records=pending,
        datasets=items,
    )


def build_dataset_overview_db(dsn: str) -> DatasetOverview:
    """读取线上事实库中每个数据域的最新登记版本。"""
    import psycopg

    with psycopg.connect(dsn) as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT ON (dataset_id)
                   dataset_id, dataset_version, status, record_count,
                   valid_record_count, pending_record_count, quality_score,
                   imported_at
            FROM dataset_versions
            ORDER BY dataset_id, imported_at DESC
            """
        ).fetchall()
    labels = {
        "jd": ("招聘岗位", "业务数据", ["JSONL", "CSV"], "企业招聘站、招聘平台"),
        "temporal": ("时间情报", "事件数据", ["JSONL"], "日报与 RSS 来源"),
        "capability": ("能力标准", "主数据", ["JSON", "JSONL", "YAML"], "职业标准与能力矩阵"),
        "evidence": ("证据记录", "分析数据", ["JSONL"], "岗位、日报与标准数据"),
        "resumes": ("简历档案", "候选人数据", ["PDF", "DOCX", "JSONL"], "候选人上传与受控导入"),
        "evaluation": ("评测样本", "评测集", ["CSV", "JSON"], "冻结标注集"),
    }
    datasets = []
    for dataset_id, version, status, records, valid, pending, quality, imported_at in rows:
        name, category, formats, source = labels.get(
            dataset_id, (dataset_id, "其他", ["JSON"], "内部导入")
        )
        datasets.append(
            DatasetItem(
                id=dataset_id,
                name=name,
                category=category,
                records=records,
                valid_records=valid,
                version=version,
                status={"IMPORTED": "可用", "FROZEN": "已冻结", "PARTIAL": "部分完成"}.get(
                    status or "", status or "未知"
                ),
                formats=formats,
                source=source,
                updated_at=imported_at.isoformat() if imported_at else "",
                quality=round(float(quality) * 100),
            )
        )
    _attach_sources(datasets)
    return DatasetOverview(
        total_datasets=len(datasets),
        total_records=sum(item.records for item in datasets),
        ready_datasets=sum(item.status in {"可用", "已审核", "已冻结"} for item in datasets),
        pending_records=sum(item.records - item.valid_records for item in datasets),
        datasets=datasets,
    )


def build_dataset_detail(dataset_id: str, dsn: str | None = None) -> DatasetDetail | None:
    overview = build_dataset_overview_db(dsn) if dsn else build_dataset_overview()
    dataset = next((item for item in overview.datasets if item.id == dataset_id), None)
    if dataset is None:
        return None

    if dsn:
        import psycopg

        with psycopg.connect(dsn) as conn:
            rows = conn.execute(
                """SELECT dataset_id, dataset_version, status, record_count,
                          valid_record_count, pending_record_count, quality_score,
                          manifest_hash, manifest, run_id, imported_at
                   FROM dataset_versions WHERE dataset_id = %s
                   ORDER BY imported_at DESC""",
                (dataset_id,),
            ).fetchall()
        versions = [
            DatasetVersion(
                dataset_id=row[0],
                version=row[1],
                status=row[2],
                records=row[3],
                valid_records=row[4],
                pending_records=row[5],
                quality=round(float(row[6]) * 100),
                manifest={
                    key: row[8][key]
                    for key in (
                        "source_id",
                        "source_type",
                        "ingestion_mode",
                        "file_count",
                        "total_bytes",
                        "dataset_version",
                        "version",
                        "seed",
                    )
                    if key in (row[8] or {})
                },
                manifest_hash=row[7],
                run_id=row[9],
                imported_at=row[10].isoformat() if row[10] else "",
            )
            for row in rows
        ]
    else:
        manifest, manifest_hash, imported_at = _manifest_summary(
            DATASET_MANIFESTS.get(dataset_id, Path())
        )
        versions = [
            DatasetVersion(
                dataset_id=dataset.id,
                version=dataset.version,
                status=dataset.status,
                records=dataset.records,
                valid_records=dataset.valid_records,
                pending_records=max(dataset.records - dataset.valid_records, 0),
                quality=dataset.quality,
                manifest=manifest,
                manifest_hash=manifest_hash,
                imported_at=imported_at or dataset.updated_at,
            )
        ]
    return DatasetDetail(dataset=dataset, versions=versions)


def _source_evidence_stats(source_id: str, dsn: str | None) -> DatasetSourceStats:
    if dsn:
        import psycopg

        with psycopg.connect(dsn) as conn:
            rows = conn.execute(
                """SELECT claim_type, quality_score, published_at, review_status
                   FROM evidence WHERE source_id = %s""",
                (source_id,),
            ).fetchall()
        reviewed = sum(row[3] in {"ACCEPTED", "MODIFIED", "REJECTED"} for row in rows)
    else:
        path = ROOT / "data" / "processed" / "evidence" / "evidence.jsonl"
        rows = []
        if path.is_file():
            for line in path.open(encoding="utf-8"):
                if not line.strip():
                    continue
                row = json.loads(line)
                if row.get("source_id") == source_id:
                    rows.append(
                        (
                            row.get("claim_type", ""),
                            row.get("quality_score", 0),
                            row.get("published_at"),
                            row.get("review_status"),
                        )
                    )
        reviewed = None

    claim_types: dict[str, int] = {}
    for row in rows:
        claim_types[str(row[0])] = claim_types.get(str(row[0]), 0) + 1
    qualities = [float(row[1]) for row in rows if row[1] is not None]
    published = [str(row[2]) for row in rows if row[2]]
    return DatasetSourceStats(
        evidence_count=len(rows),
        reviewed_evidence_count=reviewed,
        average_quality=round(sum(qualities) / len(qualities), 3) if qualities else None,
        latest_evidence_at=max(published, default=""),
        claim_types=claim_types,
    )


def build_dataset_source_detail(
    dataset_id: str, source_id: str, dsn: str | None = None
) -> DatasetSourceDetail | None:
    detail = build_dataset_detail(dataset_id, dsn)
    if detail is None:
        return None
    source = next((item for item in detail.dataset.sources if item.id == source_id), None)
    if source is None:
        return None
    stats = _source_evidence_stats(source_id, dsn)
    if stats.evidence_count == 0 and dataset_id == "jd":
        stats.attribution = "unavailable"
        stats.attribution_note = (
            "历史招聘证据记录的是发布平台 source_id，尚未保存采集通道 ID，"
            "无法把证据可靠归因到该通道。"
        )
    return DatasetSourceDetail(
        dataset_id=dataset_id,
        dataset_version=detail.dataset.version,
        source=source,
        stats=stats,
    )
