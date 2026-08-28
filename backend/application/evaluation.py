"""Evaluation overview assembled from frozen evaluation and backtest artifacts."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


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
    errors = [
        {
            "id": f"error-{index}",
            "skill": key,
            "reason": f"回测错误类型：{key}（{value} 条）",
            "priority": "high" if value >= 10 else "medium",
        }
        for index, (key, value) in enumerate(run_metrics.get("error_types", {}).items(), 1)
    ]
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
        "pending": {
            "title": "回测待复盘",
            "description": f"{len(errors)} 类错误需要人工复盘",
            "href": "/tasks",
        },
    }
