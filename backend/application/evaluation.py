"""Evaluation overview assembled from frozen evaluation and backtest artifacts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DIRECTION_LABELS = {"up": "上升", "flat": "平稳", "down": "下降"}
ERROR_CATEGORIES = {
    ("up", "down"): ("opposite", "方向判断相反", "critical"),
    ("down", "up"): ("opposite", "方向判断相反", "critical"),
    ("flat", "up"): ("missed", "未识别趋势变化", "high"),
    ("flat", "down"): ("missed", "未识别趋势变化", "high"),
    ("up", "flat"): ("false_change", "趋势变化误报", "medium"),
    ("down", "flat"): ("false_change", "趋势变化误报", "medium"),
}


def _capability_labels() -> dict[str, str]:
    path = ROOT / "data" / "processed" / "capability-matrix" / "capabilities.json"
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        item["capability_id"]: item["name"]
        for item in payload.get("capabilities", [])
        if item.get("capability_id") and item.get("name")
    }


def build_evaluation_overview() -> dict:
    samples = ROOT / "evaluation" / "samples"
    manifest_path = samples / "manifest.json"
    manifest = (
        json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    )
    datasets = [
        {
            "id": "role",
            "name": "岗位映射",
            "samples": manifest.get("role", {}).get("n", 0),
            "jobVersion": manifest.get("dataset_version", ""),
        },
        {
            "id": "domain",
            "name": "领域判定",
            "samples": manifest.get("domain", {}).get("n", 0),
            "jobVersion": manifest.get("dataset_version", ""),
        },
        {
            "id": "event",
            "name": "事件抽取",
            "samples": manifest.get("event", {}).get("n", 0),
            "jobVersion": manifest.get("dataset_version", ""),
        },
    ]
    run_path = ROOT / "data" / "processed" / "wechat-mp" / "backtest-h30.json"
    run = (
        json.loads(run_path.read_text(encoding="utf-8")) if run_path.is_file() else {"metrics": {}}
    )
    run_metrics = run.get("metrics", {})
    labels = _capability_labels()
    records = run.get("records", [])
    cases = [
        {
            "id": f"{item.get('as_of', '')}:{item.get('skill_id', '')}",
            "asOf": item.get("as_of", ""),
            "skillId": item.get("skill_id", ""),
            "skillLabel": labels.get(item.get("skill_id", ""), item.get("skill_id", "")),
            "predicted": item.get("predicted", "flat"),
            "actual": item.get("actual", "flat"),
            "hit": bool(item.get("hit")),
            "confidence": item.get("confidence", 0),
            "recent": item.get("recent", 0),
            "prior": item.get("prior", 0),
            "ruleVersion": item.get("rule_version", 1),
        }
        for item in records
    ]
    error_total = sum(run_metrics.get("error_types", {}).values())
    errors = [
        {
            "id": f"error-{index}",
            "code": key,
            "predicted": key.split("->", 1)[0],
            "actual": key.split("->", 1)[1],
            "label": (
                f"预测{DIRECTION_LABELS.get(key.split('->', 1)[0], key)}，"
                f"实际{DIRECTION_LABELS.get(key.split('->', 1)[1], key)}"
            ),
            "category": ERROR_CATEGORIES.get(
                tuple(key.split("->", 1)), ("other", "其他偏差", "medium")
            )[0],
            "categoryLabel": ERROR_CATEGORIES.get(
                tuple(key.split("->", 1)), ("other", "其他偏差", "medium")
            )[1],
            "severity": ERROR_CATEGORIES.get(
                tuple(key.split("->", 1)), ("other", "其他偏差", "medium")
            )[2],
            "count": value,
            "share": round(value / error_total, 3) if error_total else 0,
        }
        for index, (key, value) in enumerate(run_metrics.get("error_types", {}).items(), 1)
    ]
    severity_order = {"critical": 0, "high": 1, "medium": 2}
    errors.sort(key=lambda item: (severity_order.get(item["severity"], 9), -item["count"]))
    score_path = samples / "metrics.json"
    scores = json.loads(score_path.read_text(encoding="utf-8")) if score_path.is_file() else {}

    def _acc(key: str) -> float:
        value = scores.get(key, {}).get("accuracy")
        return value if isinstance(value, int | float) else 0.0

    return {
        "run": {
            "id": "backtest-h30",
            "algorithmVersion": f"temporal-v{run_metrics.get('rule_version', 1)}",
            "datasetVersion": manifest.get("dataset_version", ""),
            "status": "REVIEWING",
        },
        "datasets": datasets,
        "metrics": [
            {
                "key": "role_mapping",
                "label": "岗位映射准确率",
                "value": _acc("role_mapping"),
                "hint": "目标 ≥0.90 · evalset score",
            },
            {
                "key": "domain_judgment",
                "label": "领域判定准确率",
                "value": _acc("domain_judgment"),
                "hint": "目标 ≥0.90",
            },
            {
                "key": "event_extraction",
                "label": "事件抽取准确率",
                "value": _acc("event_extraction"),
                "hint": "目标 ≥0.90",
            },
            {
                "key": "accuracy",
                "label": "回测命中率",
                "value": run_metrics.get("accuracy", 0),
                "hint": "正确判定 / 总判定",
            },
            {
                "key": "baseline",
                "label": "平基线",
                "value": run_metrics.get("flat_baseline_accuracy", 0),
            },
        ],
        "errors": errors,
        "cases": cases,
        "summary": {
            "total": run_metrics.get("predictions", len(cases)),
            "hits": run_metrics.get("hits", sum(1 for item in cases if item["hit"])),
            "errors": error_total,
            "accuracy": run_metrics.get("accuracy", 0),
            "baselineAccuracy": run_metrics.get("flat_baseline_accuracy", 0),
        },
        "pending": {
            "title": "回测待复盘",
            "description": f"{len(errors)} 类错误需要人工复盘",
            "href": "/tasks",
        },
    }
