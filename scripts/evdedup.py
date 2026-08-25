"""evdedup: D2 事件去重——速览/正文同日重复事件的识别与标记。

用法：
    uv run scripts/evdedup.py run

去重键（docs/roadmap-data.md D2 设计）：同日 + 标题相似（归一化后精确/包含/
二元组 Jaccard>=0.55）+ 实体重合（>=1）。组内主记录 = 信息最丰（urls 多 >
summary 长 > 提及多）。所有事件保留原文，仅追加标记字段：
  duplicate_group_id / is_primary / duplicate_reason
下游消费者按 is_primary 过滤（读者已同步改造）。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).parent))

from runlog import RunContext  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "data" / "processed" / "wechat-mp" / "events.jsonl"
STATS = ROOT / "data" / "processed" / "wechat-mp" / "dedup-stats.json"

JACCARD_MIN = 0.55


def norm_title(t: str) -> str:
    t = unicodedata.normalize("NFKC", t or "")
    return re.sub(r"[\s，。！？：:·【】\[\]()（）" "''\"'-]", "", t).lower()


def bigrams(t: str) -> set[str]:
    return {t[i : i + 2] for i in range(len(t) - 1)} if len(t) > 1 else {t}


def similar(a: str, b: str) -> bool:
    na, nb = norm_title(a), norm_title(b)
    if not na or not nb:
        return False
    if na == nb or na in nb or nb in na:
        return True
    ga, gb = bigrams(na), bigrams(nb)
    inter = len(ga & gb)
    return inter / max(len(ga | gb), 1) >= JACCARD_MIN


def same_day(e1: dict, e2: dict) -> bool:
    d1 = (e1.get("published_at") or e1.get("published_date") or "")[:10]
    d2 = (e2.get("published_at") or e2.get("published_date") or "")[:10]
    return bool(d1) and d1 == d2


def entity_overlap(e1: dict, e2: dict) -> bool:
    a = set(e1.get("entities") or [])
    return bool(a & set(e2.get("entities") or []))


def richness(e: dict) -> tuple:
    return (
        len(e.get("urls") or []),
        len(e.get("summary") or ""),
        len(e.get("skill_mentions") or []),
    )


def cmd_run() -> dict:
    run = RunContext("evdedup", {"cmd": "run"})
    events = [json.loads(x) for x in EVENTS.open(encoding="utf-8")]

    # 按日分组后组内并查集聚类
    by_day: dict[str, list[int]] = defaultdict(list)
    for i, e in enumerate(events):
        day = (e.get("published_at") or e.get("published_date") or "")[:10]
        if day:
            by_day[day].append(i)

    parent = list(range(len(events)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for day, idxs in by_day.items():
        for ii in range(len(idxs)):
            for jj in range(ii + 1, len(idxs)):
                a, b = events[idxs[ii]], events[idxs[jj]]
                if similar(a["title"], b["title"]) and (
                    entity_overlap(a, b) or norm_title(a["title"]) == norm_title(b["title"])
                ):
                    union(idxs[ii], idxs[jj])

    groups: dict[int, list[int]] = defaultdict(list)
    for i in range(len(events)):
        groups[find(i)].append(i)

    dup_groups = 0
    dup_events = 0
    by_month: dict[str, int] = defaultdict(int)
    out = []
    for gi, (root_idx, members) in enumerate(sorted(groups.items()), start=1):
        if len(members) > 1:
            dup_groups += 1
            dup_events += len(members) - 1
            primary = max(members, key=lambda i: richness(events[i]))
            day = (events[members[0]].get("published_at") or "")[:7]
            by_month[day] += len(members) - 1
            for i in members:
                e = events[i]
                e["duplicate_group_id"] = f"dg{gi:05d}"
                e["is_primary"] = i == primary
                e["duplicate_reason"] = "primary" if i == primary else "same_day_similar_title"
                out.append(e)
        else:
            e = events[members[0]]
            e["duplicate_group_id"] = None
            e["is_primary"] = True
            e["duplicate_reason"] = None
            out.append(e)

    with EVENTS.open("w", encoding="utf-8") as fh:
        for e in out:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")

    metrics = {
        "events": len(events),
        "duplicate_groups": dup_groups,
        "duplicate_events": dup_events,
        "duplicate_ratio": round(dup_events / max(len(events), 1), 3),
        "by_month": dict(sorted(by_month.items())),
        "jaccard_min": JACCARD_MIN,
    }
    STATS.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    run.finish({k: v for k, v in metrics.items() if k != "by_month"})
    return metrics


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evdedup")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("run")
    parser.parse_args(argv)
    print(json.dumps(cmd_run(), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
