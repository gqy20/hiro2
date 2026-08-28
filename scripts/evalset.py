"""evalset: D9 评测集——冻结分层样本与可复现指标脚本。

用法：
    uv run scripts/evalset.py freeze     # 冻结三层样本到 evaluation/samples/（带哈希）
    uv run scripts/evalset.py score      # 标注回流后计算准确率

三层评测（人工判定为标准答案，系统输出为被评对象）：
  role    岗位映射（jd-role-map，按 method 分层 100 条）
  domain  领域判定（jd-parsed is_ai_role，按判定分层 50 条）
  event   事件抽取抽查（events 主记录，按事件类型分层 30 条）
样本一经冻结不可修改（manifest 记录哈希）；合成数据不进入（全部真实采集）。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ROLEMAP = ROOT / "data" / "processed" / "jd-opencli" / "jd-role-map.jsonl"
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
EVENTS = ROOT / "data" / "processed" / "wechat-mp" / "events.jsonl"
SAMPLES = ROOT / "evaluation" / "samples"
DATASET_VERSION = "eval-v1-20260825"
RNG_SEED = 20260825

QUOTAS_ROLE = {"exact": 15, "alias": 25, "llm": 50, "unmatched": 10}
QUOTA_DOMAIN = {"ai": 35, "non_ai": 15}
QUOTA_EVENT = 30


def _stratified(rows: list[dict], key_fn, quotas: dict[str, int]) -> list[dict]:
    rng = random.Random(RNG_SEED)
    buckets: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        buckets[key_fn(r)].append(r)
    picked: list[dict] = []
    for key, quota in quotas.items():
        pool = buckets.get(key, [])
        rng.shuffle(pool)
        picked.extend(pool[:quota])
    return picked


def _hash_rows(rows: list[dict]) -> str:
    payload = "\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def cmd_freeze() -> dict:
    run = RunContext("evalset", {"cmd": "freeze"})
    SAMPLES.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {"dataset_version": DATASET_VERSION, "seed": RNG_SEED}

    # role：岗位映射
    roles = [json.loads(x) for x in ROLEMAP.open(encoding="utf-8")]
    role_sample = _stratified(roles, lambda r: r.get("method") or "unmatched", QUOTAS_ROLE)
    with (SAMPLES / "role-mapping.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["jd_id", "职位名", "系统岗位id", "method", "映射正确?(对/错)", "修正岗位id", "备注"]
        )
        for r in role_sample:
            w.writerow(
                [r["jd_id"], r["title"], r.get("position_id") or "", r["method"], "", "", ""]
            )
    manifest["role"] = {"n": len(role_sample), "sha": _hash_rows(role_sample)}

    # domain：领域判定
    parsed = [json.loads(x) for x in PARSED.open(encoding="utf-8")]
    domain_sample = _stratified(
        parsed, lambda r: "ai" if r.get("is_ai_role") else "non_ai", QUOTA_DOMAIN
    )
    with (SAMPLES / "domain-judgment.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["jd_id", "职位名", "系统判定", "判定理由", "同意?(对/错)", "备注"])
        for r in domain_sample:
            w.writerow(
                [r["jd_id"], r["title"], r["is_ai_role"], r.get("domain_reason", ""), "", ""]
            )
    manifest["domain"] = {"n": len(domain_sample), "sha": _hash_rows(domain_sample)}

    # event：抽取抽查
    events = [
        e
        for e in (json.loads(x) for x in EVENTS.open(encoding="utf-8"))
        if e.get("is_primary", True)
    ]
    rng = random.Random(RNG_SEED)
    rng.shuffle(events)
    event_sample = events[:QUOTA_EVENT]
    with (SAMPLES / "event-extraction.csv").open("w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["event_id", "日期", "标题", "事件类型", "事实分级", "技能提及", "正确?(对/错)", "备注"]
        )
        for e in event_sample:
            w.writerow(
                [
                    e["event_id"],
                    (e.get("published_at") or "")[:10],
                    e["title"],
                    e.get("event_type", ""),
                    e.get("fact_grade", ""),
                    "; ".join(e.get("skill_mentions") or [])[:80],
                    "",
                    "",
                ]
            )
    manifest["event"] = {"n": len(event_sample), "sha": _hash_rows(event_sample)}

    (SAMPLES / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    metrics = {k: v["n"] for k, v in manifest.items() if isinstance(v, dict)}
    run.finish(metrics)
    return metrics


def _score_csv(path: Path, verdict_col: str, task_type: str, annotations: dict[str, dict]) -> dict:
    """标注来源：annotations.jsonl 优先，CSV 手工判定列为兼容回退。

    语义：ACCEPT=系统输出正确；MODIFY/REJECT=错误；UNKNOWN=无法判断不计入分母。
    """
    if not path.is_file():
        return {"error": "missing"}
    rows = list(csv.DictReader(path.open(encoding="utf-8-sig")))
    labeled = 0
    agree = 0
    for i, r in enumerate(rows):
        ann = annotations.get(f"task-{task_type}-{i:03d}")
        if ann is not None:
            if ann["decision"] == "UNKNOWN":
                continue
            labeled += 1
            if ann["decision"] == "ACCEPT":
                agree += 1
            continue
        verdict = r.get(verdict_col, "").strip()
        if verdict:
            labeled += 1
            if verdict in ("对", "是", "Y", "y"):
                agree += 1
    return {
        "total": len(rows),
        "labeled": labeled,
        "agree": agree,
        "accuracy": round(agree / labeled, 3) if labeled else None,
    }


def cmd_score() -> dict:
    run = RunContext("evalset", {"cmd": "score"})
    from backend.application.annotate import load_annotations

    annotations = load_annotations()
    result = {
        "dataset_version": DATASET_VERSION,
        "role_mapping": _score_csv(
            SAMPLES / "role-mapping.csv", "映射正确?(对/错)", "role_level", annotations
        ),
        "domain_judgment": _score_csv(
            SAMPLES / "domain-judgment.csv", "同意?(对/错)", "evidence_audit", annotations
        ),
        "event_extraction": _score_csv(
            SAMPLES / "event-extraction.csv", "正确?(对/错)", "skill_mapping", annotations
        ),
    }
    out = SAMPLES / "metrics.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    run.finish({k: v.get("accuracy") for k, v in result.items() if isinstance(v, dict)})
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evalset")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freeze")
    sub.add_parser("score")
    args = parser.parse_args(argv)
    result = cmd_freeze() if args.cmd == "freeze" else cmd_score()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
