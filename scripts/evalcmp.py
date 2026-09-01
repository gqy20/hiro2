"""evalcmp: 固定样本跨版本对比——同一批 JD 上比较两版映射输出。

用法：
    uv run scripts/evalcmp.py v1

为什么需要：evalset freeze 按 method 分层抽样，映射结果变化会导致样本漂移，
两版分数口径不可比。本脚本锚定历史冻结样本的 jd_id 与标注，
用当前映射输出重算修复/回归，得到口径严格一致的对比。
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPAIRED = ROOT / "data" / "processed" / "jd-opencli" / "jd-role-map-repaired.jsonl"
ANNOTATIONS = ROOT / "evaluation" / "annotations.jsonl"

# 判定口径允许的双答案（边界 case，两个岗位均可辩护）
BORDERLINE: dict[str, set[str | None]] = {
    "056": {"pos_01", "pos_37"},
    "087": {"pos_12", None},
}


def main() -> int:
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    samples_dir = ROOT / "evaluation" / "samples" / version
    csv_path = samples_dir / "role-mapping.csv"
    if not csv_path.is_file():
        print(f"样本不存在: {csv_path}")
        return 1
    dataset_version = f"eval-{version}-2026082{'5' if version == 'v1' else '8'}"

    rows = list(csv.DictReader(csv_path.open(encoding="utf-8-sig")))
    idx2jd = {i: r["jd_id"] for i, r in enumerate(rows)}
    anns: dict[int, dict] = {}
    for line in ANNOTATIONS.open(encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("dataset_version") == dataset_version and rec["task_id"].startswith(
            "task-role_level-"
        ):
            anns[int(rec["task_id"].rsplit("-", 1)[1])] = rec

    current = {}
    for line in REPAIRED.open(encoding="utf-8"):
        r = json.loads(line)
        current[r["jd_id"]] = r.get("position_id")

    fixed = wrong = regressed = agree_base = 0
    for idx, ann in anns.items():
        jd_id = idx2jd[idx]
        old = rows[idx]["系统岗位id"] or None
        new = current.get(jd_id)
        fix = (ann.get("corrected_payload") or {}).get("position_id")
        key = f"{idx:03d}"
        if ann["decision"] == "ACCEPT":
            # 终审锚定：ACCEPT 带 corrected_payload 时期望=锚定岗位
            # （判定对象是当时的系统输出；映射更新后期望随之对齐，消除误报回归）
            anchored = (ann.get("corrected_payload") or {}).get("position_id")
            expect = anchored if anchored is not None else old
            agree_base += 1
            if new != expect and new not in (BORDERLINE.get(key) or set()):
                regressed += 1
                print(f"回归 {key} {rows[idx]['职位名'][:26]}: {expect} -> {new}")
            continue
        target = fix if ann["decision"] == "MODIFY" else None
        if ann["decision"] == "REJECT" and "漏判" in ann.get("rationale", ""):
            target = "pos_01"
        if new == target or (key in BORDERLINE and new in (BORDERLINE[key] or set())):
            fixed += 1
        else:
            wrong += 1
            print(f"未修复 {key} {rows[idx]['职位名'][:26]}: 期望{target} 实际{new}")

    total = len(anns)
    base_pct = round(agree_base / total * 100) if total else 0
    net_pct = round((agree_base + fixed - regressed) / total * 100) if total else 0
    print(
        f"\n固定样本（{dataset_version}，{total} 条）："
        f"基线 {base_pct}% -> 当前 {net_pct}%（修复 {fixed}，未修复 {wrong}，回归 {regressed}）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
