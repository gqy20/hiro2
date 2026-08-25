"""evidence: D7 证据实体层——把三源引用升级为可回链的 Evidence 对象。

用法：
    uv run scripts/evidence.py build

产物 data/processed/evidence/evidence.jsonl，每条（contracts.md 语义）：
  evidence_id / source_id / source_span（回链：事件id、JD id、矩阵单元格）
  published_at / collected_at / content_hash / claim_type / quality_score
三源：
  ev   日报事件（主记录）——claim_type=trend_signal，质量=事实分级映射
  jd   JD 解析（AI 域）——claim_type=job_requirement，质量=解析置信
  xlsx Excel 岗位画像——claim_type=expert_baseline，质量=1.0（专家先验）
质量分规则确定性可复现；JobVersion/JobChangeSet 引用另行升级为 evidence_id。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "data" / "processed" / "wechat-mp" / "events.jsonl"
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
POSKILL = ROOT / "data" / "processed" / "capability-matrix" / "position-skills.jsonl"
OUT_DIR = ROOT / "data" / "processed" / "evidence"
OUT = OUT_DIR / "evidence.jsonl"

FACT_QUALITY = {"fact": 0.9, "report": 0.6, "opinion": 0.3}


def _hash(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def cmd_build() -> dict:
    run = RunContext("evidence", {"cmd": "build"})
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    n_ev = n_jd = n_x = 0
    with OUT.open("w", encoding="utf-8") as fh:
        # 日报事件（主记录）
        for line in EVENTS.open(encoding="utf-8"):
            e = json.loads(line)
            if not e.get("is_primary", True):
                continue
            rec = {
                "evidence_id": f"ev:{e['event_id']}",
                "source_id": "wechat-mp",
                "source_span": {
                    "type": "report_event",
                    "event_id": e["event_id"],
                    "item_id": e["item_id"],
                },
                "published_at": (e.get("published_at") or e.get("published_date")),
                "content_hash": _hash(e.get("title", "") + (e.get("summary") or "")),
                "claim_type": "trend_signal",
                "payload": {
                    "title": e.get("title"),
                    "event_type": e.get("event_type"),
                    "skill_mentions": e.get("skill_mentions") or [],
                },
                "quality_score": FACT_QUALITY.get(e.get("fact_grade"), 0.6),
                "urls": e.get("urls") or [],
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_ev += 1
        # JD 解析（AI 域）
        for line in PARSED.open(encoding="utf-8"):
            r = json.loads(line)
            if not r.get("is_ai_role"):
                continue
            rec = {
                "evidence_id": f"jd:{r['jd_id']}",
                "source_id": r.get("platform", "51job"),
                "source_span": {"type": "jd_parsed", "jd_id": r["jd_id"]},
                "published_at": r.get("publish_date"),
                "content_hash": _hash(r["jd_id"] + (r.get("title") or "")),
                "claim_type": "job_requirement",
                "payload": {
                    "title": r.get("title"),
                    "skill_mentions": r.get("skill_mentions") or [],
                    "requirements": r.get("requirements") or [],
                },
                "quality_score": 0.8,
                "domain_reason": r.get("domain_reason", ""),
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_jd += 1
        # Excel 岗位画像（专家先验）
        for line in POSKILL.open(encoding="utf-8"):
            r = json.loads(line)
            rec = {
                "evidence_id": f"xlsx:{r['position_id']}",
                "source_id": "capability-matrix",
                "source_span": {"type": "position_profile", "position_id": r["position_id"]},
                "published_at": "2026-08-19",
                "content_hash": _hash(
                    r["position_id"] + json.dumps(r.get("skill_mentions") or [], ensure_ascii=False)
                ),
                "claim_type": "expert_baseline",
                "payload": {
                    "name": r.get("name"),
                    "skill_mentions": r.get("skill_mentions") or [],
                    "responsibilities": r.get("responsibilities") or [],
                },
                "quality_score": 1.0,
            }
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            n_x += 1

    metrics = {
        "trend_signal": n_ev,
        "job_requirement": n_jd,
        "expert_baseline": n_x,
        "total": n_ev + n_jd + n_x,
    }
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evidence")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    parser.parse_args(argv)
    print(json.dumps(cmd_build(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
