"""snapshotdiff: 两个 JD 池的岗位级技能份额对比 -> JobChangeSet 草稿。

用法：
    uv run scripts/snapshotdiff.py run --base archive --obs corp
    uv run scripts/snapshotdiff.py run --base snapshots/2026-08-28 --obs corp

池标识：archive（Wayback 历史池）/ corp（现行池）/ snapshots/<日期>（快照期）。
技能侧与岗位映射来自 jd-parsed（resolved）与 jd-role-map（position_id），
两池的 jd_id 先经解析映射后 join。

输出 data/processed/jd-opencli/snapshot-changesets.json：
    每岗位 {岗位, 基准/观察窗样本量, changes: [skill, base_share, obs_share,
    change_type(add/remove/grow/shrink), 证据 jd 计数]}，供审核后喂 jobver 升版。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "jd"
PARSED = ROOT / "data" / "processed" / "jd-opencli" / "jd-parsed.jsonl"
ROLEMAP = ROOT / "data" / "processed" / "jd-opencli" / "jd-role-map.jsonl"
CAPS = ROOT / "data" / "processed" / "capability-matrix" / "capabilities.json"
OUT = ROOT / "data/processed/jd-opencli/snapshot-changesets.json"

MIN_JDS = 8  # 单池单岗位 JD 数低于此不比对（样本不足）
DELTA = 0.02  # 份额差阈值（grow/shrink）
PRESENCE = 0.005  # 出现/消失阈值（一侧占比超此、另一侧低于半值）


def pool_ids(spec: str) -> set[str]:
    """池标识 -> jd_id 集合（读 raw 池文件）。"""
    if spec == "archive":
        d = RAW / "archive"
    elif spec == "corp":
        d = RAW / "corp"
    elif spec.startswith("snapshots/"):
        d = RAW / "corp" / spec
    else:
        raise SystemExit(f"未知池: {spec}（archive / corp / snapshots/<日期>）")
    ids: set[str] = set()
    for f in sorted(d.glob("*.jsonl")):
        for line in f.open(encoding="utf-8"):
            try:
                ids.add(json.loads(line)["jd_id"])
            except Exception:  # noqa: BLE001 - 脏行跳过
                continue
    return ids


def load_side_effects() -> tuple[dict, dict]:
    """jd-parsed 的 resolved 技能表与 rolemap 岗位映射（jd_id -> ...）。"""
    skills: dict[str, list[str]] = {}
    for line in PARSED.open(encoding="utf-8"):
        r = json.loads(line)
        skills[r["jd_id"]] = [x["skill_id"] for x in (r.get("resolved") or []) if x.get("skill_id")]
    pos: dict[str, str] = {}
    for line in ROLEMAP.open(encoding="utf-8"):
        r = json.loads(line)
        if r.get("position_id"):
            pos[r["jd_id"]] = r["position_id"]
    return skills, pos


def share_by_position(ids: set[str], skills: dict, pos: dict) -> dict[str, tuple[Counter, int]]:
    """岗位 -> (技能提及计数, JD 数)。"""
    out: dict[str, tuple[Counter, int]] = {}
    for jid in ids:
        pid = pos.get(jid)
        sk = skills.get(jid)
        if not pid or not sk:
            continue
        cnt, n = out.setdefault(pid, (Counter(), 0))
        cnt.update(sk)
        out[pid] = (cnt, n + 1)
    return out


def cmd_run(base_spec: str, obs_spec: str) -> dict:
    run = RunContext("snapshotdiff", {"cmd": "run", "base": base_spec, "obs": obs_spec})
    base_ids, obs_ids = pool_ids(base_spec), pool_ids(obs_spec)
    skills, pos = load_side_effects()
    caps = {
        c["capability_id"]: c["name"]
        for c in json.loads(CAPS.read_text(encoding="utf-8"))["capabilities"]
    }

    base = share_by_position(base_ids, skills, pos)
    obs = share_by_position(obs_ids, skills, pos)

    changesets = []
    for pid in sorted(set(base) & set(obs)):
        (bc, bn), (oc, on) = base[pid], obs[pid]
        if bn < MIN_JDS or on < MIN_JDS:
            continue
        bt, ot = sum(bc.values()) or 1, sum(oc.values()) or 1
        changes = []
        for sid in set(bc) | set(oc):
            bs, os_ = bc[sid] / bt, oc[sid] / ot
            if os_ >= PRESENCE and bs < PRESENCE / 2:
                ctype = "add"
            elif bs >= PRESENCE and os_ < PRESENCE / 2:
                ctype = "remove"
            elif os_ - bs >= DELTA:
                ctype = "grow"
            elif bs - os_ >= DELTA:
                ctype = "shrink"
            else:
                continue
            changes.append(
                {
                    "skill_id": sid,
                    "name": caps.get(sid, sid),
                    "base_share": round(bs, 3),
                    "obs_share": round(os_, 3),
                    "change_type": ctype,
                    "base_mentions": bc[sid],
                    "obs_mentions": oc[sid],
                }
            )
        if not changes:
            continue
        changes.sort(key=lambda c: abs(c["obs_share"] - c["base_share"]), reverse=True)
        changesets.append(
            {
                "position_id": pid,
                "job": caps.get(pid, pid),
                "base": base_spec,
                "obs": obs_spec,
                "base_jds": bn,
                "obs_jds": on,
                "changes": changes,
                "review_status": "PENDING",
            }
        )

    OUT.write_text(
        json.dumps(
            {
                "base": base_spec,
                "obs": obs_spec,
                "changesets": changesets,
                "params": {
                    "min_jds": MIN_JDS,
                    "delta": DELTA,
                    "presence": PRESENCE,
                    "note": "数据自动检测的岗位变化草稿，发布仍需人工审核",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    metrics = {
        "base_jds": len(base_ids & set(skills)),
        "obs_jds": len(obs_ids & set(skills)),
        "positions_compared": len(changesets),
        "changes_total": sum(len(c["changes"]) for c in changesets),
        "top": [
            (c["job"], len(c["changes"]))
            for c in sorted(changesets, key=lambda x: -len(x["changes"]))[:5]
        ],
    }
    run.finish(metrics)
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="snapshotdiff")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run")
    p_run.add_argument("--base", default="archive")
    p_run.add_argument("--obs", default="corp")
    args = parser.parse_args(argv)
    result = cmd_run(args.base, args.obs)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
