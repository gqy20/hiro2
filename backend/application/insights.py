"""数据洞察 View Model：快照 Diff 检测变化 + 四层时间轴（论文→包→日报→JD）。

消费 snapshotdiff 与（arxivget + pypidl relsignal）的产物，只读组装；
检测变化为草稿语义（review_status=PENDING），发布仍走 jobver/jobpub。
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

P = Path(__file__).resolve().parents[2] / "data" / "processed"
SNAP_CS = P / "jd-opencli" / "snapshot-changesets.json"
ROLEMAP_V2 = P / "jd-opencli" / "jd-role-map-v2.jsonl"
RELSIG = P / "pypi" / "relsignal.json"
ARX = P / "arxiv" / "monthly-skills.json"
CAPS = P / "capability-matrix" / "capabilities.json"


class _VM(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DetectedChangeVM(_VM):
    skill_id: str
    name: str
    change_type: str
    base_share: float
    obs_share: float
    base_mentions: int
    obs_mentions: int


class DetectedJobVM(_VM):
    position_id: str
    job: str
    base: str
    obs: str
    base_jds: int
    obs_jds: int
    review_status: str = "PENDING"
    changes: list[DetectedChangeVM]


class DetectedChangesVM(_VM):
    base: str
    obs: str
    jobs: list[DetectedJobVM]
    changes_total: int


class TimelineRowVM(_VM):
    capability_id: str
    name: str
    arxiv_onset: str | None = None
    pypi_onset: str | None = None
    npm_onset: str | None = None
    report_onset: str | None = None
    jd_onset: str | None = None
    paper_to_jd_months: int | None = Field(default=None, description="论文首现到 JD 落地的月数")


class TimelineVM(_VM):
    rows: list[TimelineRowVM]
    note: str = (
        "各层起始月表示首次达到规模阈值的月份（论文 3 篇、生态包份额达标、日报 3 次、JD 2 次）"
    )


def _cap_names() -> dict[str, str]:
    return {
        c["capability_id"]: c["name"]
        for c in json.loads(CAPS.read_text(encoding="utf-8"))["capabilities"]
    }


_POSITION_TITLES: dict[str, str] | None = None


def _position_titles() -> dict[str, str]:
    """position_id -> 该岗位聚类下出现次数最多的 JD 标题（确定性众数，无 LLM）。"""
    global _POSITION_TITLES
    if _POSITION_TITLES is not None:
        return _POSITION_TITLES
    from collections import Counter, defaultdict

    counts: dict[str, Counter] = defaultdict(Counter)
    if ROLEMAP_V2.is_file():
        for line in ROLEMAP_V2.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            pid, title = r.get("position_id"), (r.get("title") or "").strip()
            if pid and title:
                counts[pid][title] += 1
    _POSITION_TITLES = {pid: counter.most_common(1)[0][0] for pid, counter in counts.items()}
    return _POSITION_TITLES


def _display_title(pid: str, titles: dict[str, str], fallback: str) -> str:
    """展示用岗位名：众数标题截断到 24 字，解析失败回退原始字段。"""
    title = titles.get(pid, fallback)
    return title[:24] + "…" if len(title) > 24 else title


def build_detected_changes() -> DetectedChangesVM:
    data = json.loads(SNAP_CS.read_text(encoding="utf-8"))
    titles = _position_titles()
    jobs = [
        DetectedJobVM(
            position_id=c["position_id"],
            job=_display_title(c["position_id"], titles, c["job"]),
            base=c["base"],
            obs=c["obs"],
            base_jds=c["base_jds"],
            obs_jds=c["obs_jds"],
            review_status=c.get("review_status", "PENDING"),
            changes=[DetectedChangeVM(**ch) for ch in c["changes"]],
        )
        for c in data.get("changesets", [])
    ]
    return DetectedChangesVM(
        base=data.get("base", ""),
        obs=data.get("obs", ""),
        jobs=jobs,
        changes_total=sum(len(j.changes) for j in jobs),
    )


def _months_between(a: str | None, b: str | None) -> int | None:
    if not a or not b:
        return None
    y1, m1, y2, m2 = int(a[:4]), int(a[5:7]), int(b[:4]), int(b[5:7])
    return (y2 - y1) * 12 + (m2 - m1)


def build_timeline() -> TimelineVM:
    names = _cap_names()
    rel = json.loads(RELSIG.read_text(encoding="utf-8")) if RELSIG.is_file() else {"rows": []}
    arx_onset: dict[str, str] = {}
    if ARX.is_file():
        monthly = json.loads(ARX.read_text(encoding="utf-8"))["monthly"]
        for cap in names:
            for m in sorted(monthly):
                if monthly[m].get(cap, 0) >= 3:
                    arx_onset[cap] = m
                    break
    rows = []
    for r in rel.get("rows", []):
        cap = r["capability_id"]
        a = arx_onset.get(cap)
        p2j = _months_between(a, r.get("jd_onset") or "")
        rows.append(
            TimelineRowVM(
                capability_id=cap,
                name=names.get(cap, cap),
                arxiv_onset=a,
                pypi_onset=r.get("rel_onset"),
                npm_onset=r.get("npm_share_onset"),
                report_onset=r.get("report_onset"),
                jd_onset=r.get("jd_onset"),
                paper_to_jd_months=p2j,
            )
        )
    rows.sort(key=lambda r: -(r.paper_to_jd_months or -1))
    return TimelineVM(rows=rows)
