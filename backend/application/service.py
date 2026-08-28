"""Application Use Case 与 View Model（ADR 0006：OpenAPI 为唯一契约源）。

View Model 字段与前端既有类型（apps/web/lib/job-update.ts 等）逐一对齐，
camelCase 别名序列化；映射与联查（证据摘录等）都在本层完成，
API 层与数据层互不感知。
"""

from __future__ import annotations

import time
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .repos import DataRepository, build_repository

SourceType = Literal["招聘 JD", "技术日报", "职业标准"]
EvidenceStance = Literal["支持", "反证"]
ReviewStatus = Literal["reviewing", "accepted", "rejected", "needs_evidence"]
ChangeKind = Literal["added", "removed", "modified"]


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(w.capitalize() for w in rest)


class _VM(BaseModel):
    model_config = ConfigDict(alias_generator=_camel, populate_by_name=True)


class EvidenceVM(_VM):
    id: str
    source: str
    source_type: SourceType
    published_at: str | None = None
    collected_at: str | None = None
    quality: float
    excerpt: str
    full_text: str
    source_url: str | None = None
    stance: EvidenceStance = "支持"


class ChangeItemVM(_VM):
    id: str
    kind: ChangeKind
    title: str
    detail: str
    confidence: float
    status: ReviewStatus
    evidence: list[EvidenceVM]


class ProgressStepVM(_VM):
    id: str
    label: str
    detail: str
    state: Literal["finished", "active", "waiting"]


class JobUpdateVM(_VM):
    fixture_version: str
    mode: Literal["synthetic"] = "synthetic"
    run: dict
    context: dict
    summary: dict
    changes: list[ChangeItemVM]
    progress_steps: list[ProgressStepVM]


class CandidateVM(_VM):
    id: str
    title: str
    summary: str
    confidence: float
    companies: int
    source_count: int
    status: ReviewStatus
    why_new: str
    responsibilities: list[str]
    required_skills: list[str]
    preferred_skills: list[str]
    scenarios: list[str]
    evidence: list[EvidenceVM]


class NewJobsVM(_VM):
    fixture_version: str
    mode: Literal["synthetic"] = "synthetic"
    run_id: str
    candidates: list[CandidateVM]


_SOURCE_TYPE: dict[str, SourceType] = {"jd": "招聘 JD", "ev": "技术日报", "xlsx": "职业标准"}
_DEFAULT_SOURCE_TYPE: SourceType = "技术日报"


class ApplicationService:
    """Use Case：组装 View Model（读 Repository，联查摘录，映射枚举）。"""

    def __init__(self, repo: DataRepository | None = None) -> None:
        self.repo = repo or build_repository()
        self._events_cache: dict | None = None
        self._jd_cache: dict | None = None

    # ponytail: 全表联查在实例内只拉一次；原先每条证据各重扫全表（14k 行 x 32 次 ~15s）。
    # 缓存在实例上：请求内新建的实例（build_dashboard）天然新鲜；main.py 长驻实例
    # 会陈旧到重启，数据入库走 dbimport + 重启，可接受。
    def _events_primary(self) -> dict:
        if self._events_cache is None:
            self._events_cache = self.repo.events_primary()
        return self._events_cache

    def _jd_parsed(self) -> dict:
        if self._jd_cache is None:
            self._jd_cache = self.repo.jd_parsed()
        return self._jd_cache

    # ---------- 证据 ----------

    def _evidence_vm(self, ev: dict) -> EvidenceVM:
        prefix = ev["evidence_id"].split(":", 1)[0]
        payload = ev.get("payload") or {}
        span = ev.get("source_span") or {}
        excerpt, full, url = "", "", None
        if prefix == "ev":
            src = self._events_primary().get(span.get("event_id", ""), {})
            full = src.get("summary") or payload.get("title") or ""
            url = (ev.get("urls") or [None])[0]
        elif prefix == "jd":
            src = self._jd_parsed().get(span.get("jd_id", ""), {})
            full = "；".join((src.get("responsibilities") or []) + (src.get("requirements") or []))
            url = None
        else:
            full = "；".join(payload.get("responsibilities") or [])
        excerpt = (full or payload.get("title") or "")[:160]
        return EvidenceVM(
            id=ev["evidence_id"],
            source=ev.get("source_id", ""),
            source_type=_SOURCE_TYPE.get(prefix, _DEFAULT_SOURCE_TYPE),
            published_at=ev.get("published_at"),
            collected_at=ev.get("published_at"),
            quality=ev.get("quality_score", 0.6),
            excerpt=excerpt,
            full_text=full or excerpt,
            source_url=url,
        )

    def evidence_by_id(self, evidence_id: str) -> EvidenceVM | None:
        for ev in self.repo.evidence():
            if ev["evidence_id"] == evidence_id:
                return self._evidence_vm(ev)
        return None

    # ---------- 岗位更新（主案例 2） ----------

    _KIND: dict[str, ChangeKind] = {
        "add": "added",
        "remove": "removed",
        "promote": "modified",
        "demote": "modified",
    }

    def job_update(self, state: str = "ready") -> JobUpdateVM:
        cs = self.repo.job_changeset()
        if state == "empty":
            return JobUpdateVM(
                fixture_version="v2",
                run={
                    "id": cs.get("changeset_id", ""),
                    "datasetVersion": "eval-v1",
                    "status": "REVIEWING",
                },
                context={
                    "jobTitle": "AI 应用工程师（综合）",
                    "baselineVersion": "v1 基准窗 2026-03~04",
                    "targetVersion": "v2 观察窗 2026-06~07",
                    "timeWindow": cs.get("obs_window", ""),
                },
                summary={"validSamples": 0, "companies": 0, "evidenceSources": 0},
                changes=[],
                progress_steps=[],
            )
        # ponytail: 全量证据索引只建一次，原先每个 change 各查一遍导致 N 次 14k 行全表扫描（~15s）。
        ev_index = {e["evidence_id"]: e for e in self.repo.evidence()}
        changes = [
            ChangeItemVM(
                id=f"chg-{c['skill_id']}",
                kind=self._KIND.get(c["change_type"], "modified"),
                title=c["name"],
                detail=(
                    f"{c.get('base_mentions', 0)} -> {c.get('obs_mentions', 0)} 次提及，"
                    f"份额 {c.get('base_share', 0):.1%} -> {c.get('obs_share', 0):.1%}"
                ),
                confidence=round(min(0.5 + (c.get("obs_mentions", 0) or 0) / 40, 0.95), 2),
                status="reviewing",
                evidence=[self._evidence_vm(e) for e in self._jd_evidence(c, ev_index)],
            )
            for c in cs.get("changes", [])
        ]
        sample = cs.get("sample") or {}
        return JobUpdateVM(
            fixture_version="v2",
            run={
                "id": cs.get("changeset_id", ""),
                "datasetVersion": "eval-v1",
                "status": "REVIEWING",
            },
            context={
                "jobTitle": "AI 应用工程师（综合）",
                "baselineVersion": "v1 基准窗 2026-03~04",
                "targetVersion": "v2 观察窗 2026-06~07",
                "timeWindow": f"{cs.get('base_window', '')} vs {cs.get('obs_window', '')}",
            },
            summary={
                "validSamples": (sample.get("base_jds", 0) or 0) + (sample.get("obs_jds", 0) or 0),
                "companies": 27,
                "evidenceSources": 2,
            },
            changes=changes,
            progress_steps=[
                ProgressStepVM(
                    id="s1",
                    label="基准窗数据",
                    detail=f"{sample.get('base_jds', 0)} 条",
                    state="finished",
                ),
                ProgressStepVM(
                    id="s2",
                    label="观察窗数据",
                    detail=f"{sample.get('obs_jds', 0)} 条",
                    state="finished",
                ),
                ProgressStepVM(
                    id="s3", label="Diff 生成", detail=f"{len(changes)} 项变化", state="finished"
                ),
                ProgressStepVM(id="s4", label="人工审核", detail="待审核", state="active"),
            ],
        )

    def _jd_evidence(self, change: dict, ev_index: dict[str, dict]) -> list[dict]:
        out = []
        for eid in change.get("evidence_ids") or []:
            ev = ev_index.get(eid)
            if ev:
                out.append(ev)
        return out[:3]

    # ---------- 新岗位候选（主案例 1） ----------

    def emerging_jobs(self) -> NewJobsVM:
        em = self.repo.emerging().get("evidence", {})
        card = em.get("definition_card", {})
        diff = em.get("diffusion", {})
        emerge = em.get("emergence", {})
        resp = [x["phrase"] for x in card.get("core_responsibilities", [])]
        req = [x["phrase"] for x in card.get("required_skills", [])]
        pref = [x["phrase"] for x in card.get("preferred_skills", [])]
        scen = [x["name"] for x in card.get("typical_industries", [])]
        why = (
            f"技能组合与最近邻余弦 0.788/0.645 可区分；日报信号强度 "
            f"{em.get('signal_precedence', {}).get('signal_total_weight', 0):.0f}（全域第一），"
            f"领先 JD 落地 184 天（下界）"
        )
        return NewJobsVM(
            fixture_version="v2",
            run_id="newjob-agent-20260825",
            candidates=[
                CandidateVM(
                    id="emerging-agent",
                    title="AI Agent 工程师",
                    summary=(
                        f"{emerge.get('jd_total', 0)} 条 JD、"
                        f"{emerge.get('title_variants', 0)} 种标题变体、月度 1->7 增长"
                    ),
                    confidence=0.92,
                    companies=diff.get("distinct_companies", 0),
                    source_count=2,
                    status="reviewing",
                    why_new=why,
                    responsibilities=resp,
                    required_skills=req,
                    preferred_skills=pref,
                    scenarios=scen,
                    evidence=self._agent_evidence(),
                )
            ],
        )

    def _agent_evidence(self) -> list[EvidenceVM]:
        picks: list[dict] = []
        for ev in self.repo.evidence():
            if len(picks) >= 3:
                break
            if ev["evidence_id"].startswith(("jd:", "xlsx:")):
                picks.append(ev)
        return [self._evidence_vm(e) for e in picks]

    # ---------- 审核（append-only，ADR 0006） ----------

    def submit_review(self, target_id: str, decision: str, note: str = "") -> dict:
        action = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "target_id": target_id,
            "decision": decision,
            "note": note,
        }
        self.repo.append_review(action)
        return {"accepted": True, **action}
