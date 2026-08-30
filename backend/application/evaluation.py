"""Evaluation overview assembled from frozen evaluation and backtest artifacts."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from backend.application.annotate import load_annotations

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
EVENT_TYPE_LABELS = {
    "adoption": "行业应用",
    "model_release": "模型发布",
    "open_source": "开源发布",
    "policy": "政策监管",
    "productization": "产品动态",
    "research": "研究进展",
    "rumor": "未证实消息",
}
FACT_GRADE_LABELS = {"fact": "已确认事实", "report": "媒体报道"}


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


def _position_labels() -> dict[str, str]:
    path = ROOT / "data" / "processed" / "capability-matrix" / "positions.jsonl"
    if not path.is_file():
        return {}
    labels: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item.get("position_id") and item.get("name"):
            labels[item["position_id"]] = item["name"]
    return labels


def _sample_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _sample_evaluations(samples: Path, scores: dict) -> list[dict]:
    annotations = load_annotations()
    positions = _position_labels()
    specs = [
        {
            "id": "role",
            "name": "岗位映射",
            "description": "检查岗位是否映射到正确的标准岗位。",
            "metric": "role_mapping",
            "file": "role-mapping.csv",
            "task": "role_level",
        },
        {
            "id": "domain",
            "name": "领域判定",
            "description": "检查职位是否被正确识别为 AI 相关岗位。",
            "metric": "domain_judgment",
            "file": "domain-judgment.csv",
            "task": "evidence_audit",
        },
        {
            "id": "event",
            "name": "事件抽取",
            "description": "检查事件类型、事实等级和技能提及。",
            "metric": "event_extraction",
            "file": "event-extraction.csv",
            "task": "skill_mapping",
        },
    ]
    result = []
    for spec in specs:
        rows = _sample_rows(samples / spec["file"])
        cases = []
        for index, row in enumerate(rows):
            task_id = f"task-{spec['task']}-{index:03d}"
            annotation = annotations.get(task_id, {})
            decision = annotation.get("decision", "UNKNOWN")
            corrected = annotation.get("corrected_payload") or {}
            if spec["id"] == "role":
                position_id = row.get("系统岗位id", "")
                system_result = positions.get(position_id, position_id) if position_id else "未映射"
                corrected_id = corrected.get("position_id", "")
                expected_result = (
                    positions.get(corrected_id, corrected_id)
                    if corrected_id
                    else ("不应映射" if decision == "REJECT" else "")
                )
                detail = f"映射方式：{row.get('method', '未登记')}"
                source_id = row.get("jd_id", "")
                title = row.get("职位名", "")
            elif spec["id"] == "domain":
                is_ai = row.get("系统判定", "").lower() == "true"
                system_result = "AI 相关岗位" if is_ai else "非 AI 岗位"
                expected_result = ""
                detail = row.get("判定理由", "")
                source_id = row.get("jd_id", "")
                title = row.get("职位名", "")
            else:
                event_type = row.get("事件类型", "未登记")
                fact_grade = row.get("事实分级", "未登记")
                system_result = (
                    f"{EVENT_TYPE_LABELS.get(event_type, event_type)} · "
                    f"{FACT_GRADE_LABELS.get(fact_grade, fact_grade)}"
                )
                expected_result = ""
                skills = row.get("技能提及", "") or "无技能提及"
                detail = f"技能提及：{skills}"
                source_id = row.get("event_id", "")
                title = row.get("标题", "")
            rationale = annotation.get("rationale", "").removeprefix("[AI预标注批量采纳] ")
            if spec["id"] == "domain" and decision in {"MODIFY", "REJECT"}:
                rationale = "该样本与系统判定存在分歧，需重新确认岗位范围。"
            cases.append(
                {
                    "id": task_id,
                    "sourceId": source_id,
                    "title": title,
                    "date": row.get("日期", ""),
                    "decision": decision,
                    "systemResult": system_result,
                    "expectedResult": expected_result,
                    "detail": detail,
                    "rationale": rationale,
                    "reviewer": annotation.get("reviewer_id", ""),
                }
            )
        metric = scores.get(spec["metric"], {})
        result.append(
            {
                "id": spec["id"],
                "name": spec["name"],
                "description": spec["description"],
                "summary": {
                    "total": metric.get("total", len(cases)),
                    "reviewed": metric.get("labeled", 0),
                    "correct": metric.get("agree", 0),
                    "errors": max(0, metric.get("labeled", 0) - metric.get("agree", 0)),
                    "accuracy": metric.get("accuracy") or 0,
                },
                "cases": cases,
            }
        )
    return result


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
        {
            "id": "trend",
            "name": "趋势回测",
            "samples": 0,
            "jobVersion": "",
        },
    ]
    run_path = ROOT / "data" / "processed" / "wechat-mp" / "backtest-h30.json"
    run = (
        json.loads(run_path.read_text(encoding="utf-8")) if run_path.is_file() else {"metrics": {}}
    )
    run_metrics = run.get("metrics", {})
    datasets[-1]["samples"] = run_metrics.get("predictions", 0)
    datasets[-1]["jobVersion"] = f"temporal-v{run_metrics.get('rule_version', 1)}"
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
    sample_evaluations = _sample_evaluations(samples, scores)

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
        "sampleEvaluations": sample_evaluations,
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
