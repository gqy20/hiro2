"""简历档案域：上传文件落盘 data/objects/resumes/，元数据与画像追加 JSONL。

离线优先（ADR 0002）：文件为权威，PG 同步留待事实主库需要时再加
（append_review 同款模式）。导入（imported）档案只登记文件不解析，
按需补解析的成本留给用户决策。
"""

from __future__ import annotations

import json
import os
import shutil
import time
import uuid
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[2]
OBJECTS = Path(os.getenv("RESUME_OBJECTS_DIR", str(ROOT / "data" / "objects" / "resumes")))
ARCHIVE = Path(
    os.getenv(
        "RESUME_ARCHIVE_PATH",
        str(ROOT / "data" / "processed" / "candidates" / "resume-archive.jsonl"),
    )
)

_LIST_FIELDS = (
    "resume_id",
    "filename",
    "size",
    "suffix",
    "uploaded_at",
    "source",
    "sample_type",
    "parse_mode",
    "parse_error",
    "stats",
)
_WRITE_LOCK = Lock()


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def _sample_type(record: dict) -> str:
    if record.get("sample_type"):
        return str(record["sample_type"])
    filename = str(record.get("filename", "")).lower()
    source = str(record.get("source", ""))
    if filename.startswith("div_") or source in {"synthetic", "generated"}:
        return "synthetic"
    if source == "upload":
        return "uploaded"
    if source in {"anonymized", "authorized"}:
        return "anonymized"
    return "controlled"


def _append(record: dict) -> None:
    with _WRITE_LOCK:
        ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
        with ARCHIVE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def save_to_archive(content: bytes, filename: str, parse_result: dict) -> dict:
    """上传解析成功后入档：文件入 objects，画像与原文入 JSONL。"""
    resume_id = f"res-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    suffix = Path(filename).suffix.lower()
    OBJECTS.mkdir(parents=True, exist_ok=True)
    stored = OBJECTS / f"{resume_id}{suffix}"
    stored.write_bytes(content)
    record = {
        "resume_id": resume_id,
        "filename": filename,
        "size": len(content),
        "suffix": suffix,
        "uploaded_at": _now(),
        "source": "upload",
        "sample_type": "uploaded",
        "stats": parse_result.get("stats", {}),
        "profile": parse_result.get("profile", {}),
        "raw_text": parse_result.get("rawText", ""),
    }
    _append(record)
    return record


def import_file(src: Path, source_label: str = "imported") -> dict:
    """登记既有文件入档（不解析）；同名校验避免重复导入。"""
    if not src.is_file():
        raise FileNotFoundError(src)
    if _find_by_filename(src.name) is not None:
        raise ValueError(f"已入档：{src.name}")
    content = src.read_bytes()
    resume_id = f"res-{time.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8]}"
    OBJECTS.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, OBJECTS / f"{resume_id}{src.suffix.lower()}")
    record = {
        "resume_id": resume_id,
        "filename": src.name,
        "size": len(content),
        "suffix": src.suffix.lower(),
        "uploaded_at": _now(),
        "source": source_label,
        "sample_type": "synthetic" if src.name.lower().startswith("div_") else "controlled",
        "stats": None,
        "profile": None,
        "raw_text": "",
    }
    _append(record)
    return record


def _load_all() -> list[dict]:
    if not ARCHIVE.is_file():
        return []
    return [json.loads(x) for x in ARCHIVE.open(encoding="utf-8") if x.strip()]


def _find_by_filename(filename: str) -> dict | None:
    return next((r for r in _load_all() if r["filename"] == filename), None)


def list_archive() -> list[dict]:
    """档案列表（轻字段，最新在前）。"""
    latest: dict[str, dict] = {}
    for row in _load_all():
        latest[row["resume_id"]] = row
    rows = [
        {**{k: r.get(k) for k in _LIST_FIELDS}, "sample_type": _sample_type(r)}
        for r in latest.values()
    ]
    rows.reverse()
    return rows


def get_archive(resume_id: str) -> dict | None:
    return next((r for r in reversed(_load_all()) if r["resume_id"] == resume_id), None)


def update_archive(resume_id: str, patch: dict) -> dict:
    """追加式更新档案记录，保留原始文件与历史记录。"""
    rows = _load_all()
    current = next((r for r in reversed(rows) if r["resume_id"] == resume_id), None)
    if current is None:
        raise KeyError(resume_id)
    updated = {**current, **patch, "resume_id": resume_id}
    _append(updated)
    return updated


def get_stored_file(resume_id: str) -> Path | None:
    """按不可猜测的 resume_id 定位原文件，不接受任意路径输入。"""
    return next(OBJECTS.glob(f"{resume_id}.*"), None)
