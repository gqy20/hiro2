"""annotate: 评测标注持久化——append-only 标注记录。

冻结样本 CSV 不可修改（manifest 哈希保护）；人工决策以
EvaluationAnnotation（见 contracts.md）逐行追加到
evaluation/annotations.jsonl，score 计算时按 task_id 回流。
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ANNOTATIONS = ROOT / "evaluation" / "annotations.jsonl"
PRELABELS = ROOT / "evaluation" / "prelabels.jsonl"
DATASET_VERSION = "eval-v2-20260828"

VALID_DECISIONS = ("ACCEPT", "MODIFY", "REJECT", "UNKNOWN")


def load_prelabels() -> dict[str, dict[str, Any]]:
    """读取 AI 预标注建议（scripts/prelabel.py 产物），返回 task_id -> 建议。

    建议只是候选，不计入指标；人工提交后才写入 annotations。
    """
    latest: dict[str, dict[str, Any]] = {}
    if not PRELABELS.is_file():
        return latest
    for line in PRELABELS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        latest[rec["task_id"]] = rec
    return latest


def load_annotations() -> dict[str, dict[str, Any]]:
    """读取标注记录，返回 task_id -> 最新一条标注（仅当前数据集版本）。"""
    latest: dict[str, dict[str, Any]] = {}
    if not ANNOTATIONS.is_file():
        return latest
    for line in ANNOTATIONS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        if rec.get("dataset_version") != DATASET_VERSION:
            continue
        latest[rec["task_id"]] = rec
    return latest


def submit_annotation(
    task_id: str,
    decision: str,
    rationale: str = "",
    reviewer_id: str = "local",
    error_type: str | None = None,
    corrected_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """追加一条标注记录（append-only，不覆盖历史决策）。"""
    if decision not in VALID_DECISIONS:
        raise ValueError(f"非法 decision: {decision}")
    rec: dict[str, Any] = {
        "annotation_id": f"ann-{uuid.uuid4().hex[:12]}",
        "task_id": task_id,
        "dataset_version": DATASET_VERSION,
        "reviewer_id": reviewer_id,
        "decision": decision,
        "rationale": rationale,
        "error_type": error_type,
        "corrected_payload": corrected_payload,
        "submitted_at": datetime.now(UTC).isoformat(),
    }
    ANNOTATIONS.parent.mkdir(parents=True, exist_ok=True)
    with ANNOTATIONS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec
