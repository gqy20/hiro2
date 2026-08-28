"""数据资产目录 View Model，聚合 manifest 与处理产物供内部治理界面使用。"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]


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


class DatasetOverview(BaseModel):
    total_datasets: int = 0
    total_records: int = 0
    ready_datasets: int = 0
    pending_records: int = 0
    datasets: list[DatasetItem] = Field(default_factory=list)


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
                json.loads(line)
                for line in archive_path.open(encoding="utf-8")
                if line.strip()
            ]
        latest_rows = {
            str(row.get("resume_id")): row
            for row in archive_rows
            if row.get("resume_id")
        }
        parsed = sum(bool(row.get("profile")) for row in latest_rows.values())
        items[items.index(resume_item)] = resume_item.model_copy(
            update={"records": len(latest_rows), "valid_records": parsed}
        )
    total = sum(item.records for item in items)
    ready = sum(item.status in {"可用", "已审核", "已冻结"} for item in items)
    pending = sum(item.records - item.valid_records for item in items)
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
                    status, status
                ),
                formats=formats,
                source=source,
                updated_at=imported_at.isoformat() if imported_at else "",
                quality=round(float(quality) * 100),
            )
        )
    return DatasetOverview(
        total_datasets=len(datasets),
        total_records=sum(item.records for item in datasets),
        ready_datasets=sum(item.status in {"可用", "已审核", "已冻结"} for item in datasets),
        pending_records=sum(item.records - item.valid_records for item in datasets),
        datasets=datasets,
    )
