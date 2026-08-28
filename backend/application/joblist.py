"""joblist: 已发布岗位版本列表 VM——求职区目标岗位页与岗位选择器数据源。

数据源：
  - data/processed/jobversions/published/*.json（不可变已发布版本）
  - data/processed/capability-matrix/positions.jsonl（岗位职责说明）
每个 job_id 只保留最新发布版本；position_id 从 job_id 内嵌的 pos_XX 解析。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from pydantic import Field

from .temporal_vm import _VM

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = ROOT / "data" / "processed" / "jobversions" / "published"
POSITIONS = ROOT / "data" / "processed" / "capability-matrix" / "positions.jsonl"


class PublishedJobItem(_VM):
    job_id: str
    version_id: str
    title: str
    group: str = ""
    duty: str = ""
    required_count: int = 0
    preferred_count: int = 0
    valid_from: str = ""
    published_at: str = ""


class PublishedJobsVM(_VM):
    jobs: list[PublishedJobItem] = Field(default_factory=list)
    total: int = 0


def _first_duty(summary: str) -> str:
    """从岗位 summary 提取第一条职责，限制 60 字。"""
    m = re.search(r"1[.、]\s*(.+)", summary)
    duty = m.group(1).strip() if m else summary.strip().splitlines()[0] if summary else ""
    return duty[:60] + ("…" if len(duty) > 60 else "")


def build_published_jobs() -> PublishedJobsVM:
    positions: dict[str, dict] = {}
    if POSITIONS.is_file():
        for line in POSITIONS.read_text(encoding="utf-8").splitlines():
            if line.strip():
                p = json.loads(line)
                positions[p["position_id"]] = p

    latest: dict[str, dict] = {}
    if PUBLISHED.is_dir():
        for f in sorted(PUBLISHED.glob("*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            if d.get("status") != "PUBLISHED":
                continue
            prev = latest.get(d["job_id"])
            if prev is None or d.get("published_at", "") > prev.get("published_at", ""):
                latest[d["job_id"]] = d

    jobs: list[PublishedJobItem] = []
    for d in sorted(latest.values(), key=lambda x: x["job_id"]):
        m = re.search(r"pos_\d+", d["job_id"])
        pos = positions.get(m.group(0)) if m else None
        jobs.append(
            PublishedJobItem(
                job_id=d["job_id"],
                version_id=d["version_id"],
                title=d["title"],
                group=pos.get("group", "") if pos else "",
                duty=_first_duty(pos.get("summary", "")) if pos else "",
                required_count=len(d.get("required_skill_ids", [])),
                preferred_count=len(d.get("preferred_skill_ids", [])),
                valid_from=d.get("valid_from", ""),
                published_at=d.get("published_at", ""),
            )
        )
    return PublishedJobsVM(jobs=jobs, total=len(jobs))
