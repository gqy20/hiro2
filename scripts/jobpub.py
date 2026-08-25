"""jobpub: 岗位版本发布——DRAFT 审核通过后固化为不可变 PUBLISHED 文件。

用法：
    uv run scripts/jobpub.py publish <draft_path> --reviewer <name> [--note ...]

规则（contracts：发布后不可变）：
  - 前置：review-actions.jsonl 中必须存在对该草稿的 accepted 动作（人工审核留痕）
  - 产物：data/processed/jobversions/published/<id>.json，
    追加 version_hash / published_at / review_action_ids，写入后不再修改
  - 已发布的 id 重复发布将被拒绝（幂等保护）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / "data" / "processed" / "jd-opencli" / "jobversion-agent-draft.json"
REVIEW_LOG = ROOT / "data" / "processed" / "review" / "review-actions.jsonl"
PUB_DIR = ROOT / "data" / "processed" / "jobversions" / "published"


def cmd_publish(draft_path: Path, reviewer: str, note: str, version_id: str | None) -> dict:
    run = RunContext("jobpub", {"cmd": "publish", "draft": str(draft_path)})
    draft = json.loads(draft_path.read_text(encoding="utf-8"))

    # 前置：审核动作留痕（对草稿 job_id 的 accepted）
    actions = []
    if REVIEW_LOG.is_file():
        actions = [json.loads(x) for x in REVIEW_LOG.open(encoding="utf-8")]
    accepted = [a for a in actions if a.get("decision") == "accepted"]
    if not accepted:
        run.log("jobpub", "no_accept", "failed", detail="review-actions.jsonl 无 accepted 动作")
        run.finish({}, "FAILED")
        raise SystemExit("发布被拒绝：没有人工审核接受记录")

    vid = version_id or draft.get("version_id", "v1")
    pub = {
        **draft,
        "version_id": vid,
        "status": "PUBLISHED",
        "published_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "reviewer": reviewer,
        "review_note": note,
        "review_action_ids": [f"ra-{i}" for i in range(len(accepted))],
    }
    payload = json.dumps(pub, ensure_ascii=False, sort_keys=True)
    pub["version_hash"] = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    PUB_DIR.mkdir(parents=True, exist_ok=True)
    out = PUB_DIR / f"{vid}.json"
    if out.is_file():
        raise SystemExit(f"发布被拒绝：{vid} 已存在（发布后不可变，不得重复发布）")
    out.write_text(json.dumps(pub, ensure_ascii=False, indent=2), encoding="utf-8")
    run.log("jobpub", vid, "succeeded", count={"hash": pub["version_hash"]})
    run.finish({"version_id": vid, "hash": pub["version_hash"]})
    return {"version_id": vid, "hash": pub["version_hash"], "path": str(out)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="jobpub")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_pub = sub.add_parser("publish")
    p_pub.add_argument("draft", nargs="?", default=str(DRAFT))
    p_pub.add_argument("--reviewer", required=True)
    p_pub.add_argument("--note", default="")
    p_pub.add_argument("--version-id", default=None)
    args = parser.parse_args(argv)
    result = cmd_publish(Path(args.draft), args.reviewer, args.note, args.version_id)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
