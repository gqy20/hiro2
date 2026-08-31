"""Application Use Case 与 View Model（ADR 0006：OpenAPI 为唯一契约源）。

View Model 字段与前端既有类型（apps/web/lib/job-update.ts 等）逐一对齐，
camelCase 别名序列化；映射与联查（证据摘录等）都在本层完成，
API 层与数据层互不感知。
"""

from __future__ import annotations

import json
import time
from typing import Literal

from .evidence_view import _VM, EvidenceVM, evidence_to_vm
from .repos import DataRepository, build_repository

ReviewStatus = Literal["reviewing", "accepted", "rejected", "needs_evidence"]
ChangeKind = Literal["added", "removed", "modified"]


class EvidenceSearchItemVM(EvidenceVM):
    claim_type: str
    review_status: str


class EvidenceSearchResultVM(_VM):
    items: list[EvidenceSearchItemVM]
    total: int
    offset: int
    limit: int


class EvidenceFacetItemVM(_VM):
    value: str
    count: int


class EvidenceFacetsVM(_VM):
    sources: list[EvidenceFacetItemVM]
    claim_types: list[EvidenceFacetItemVM]
    review_statuses: list[EvidenceFacetItemVM]
    earliest_published_at: str = ""
    latest_published_at: str = ""


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
        return evidence_to_vm(ev, self._events_primary(), self._jd_parsed())

    def evidence_by_id(self, evidence_id: str) -> EvidenceVM | None:
        for ev in self.repo.evidence():
            if ev["evidence_id"] == evidence_id:
                return self._evidence_vm(ev)
        return None

    def search_evidence(
        self,
        *,
        source_id: str = "",
        claim_type: str = "",
        review_status: str = "",
        date_from: str = "",
        date_to: str = "",
        query: str = "",
        offset: int = 0,
        limit: int = 50,
    ) -> EvidenceSearchResultVM:
        needle = query.strip().casefold()
        matches: list[dict] = []
        for evidence in self.repo.evidence():
            if source_id and evidence.get("source_id") != source_id:
                continue
            if claim_type and evidence.get("claim_type") != claim_type:
                continue
            status = str(evidence.get("review_status") or "PENDING")
            if review_status and status != review_status:
                continue
            published_date = str(evidence.get("published_at") or "")[:10]
            if date_from and (not published_date or published_date < date_from):
                continue
            if date_to and (not published_date or published_date > date_to):
                continue
            if needle:
                searchable = " ".join(
                    (
                        str(evidence.get("evidence_id", "")),
                        str(evidence.get("source_id", "")),
                        json.dumps(evidence.get("payload") or {}, ensure_ascii=False),
                    )
                ).casefold()
                if needle not in searchable:
                    continue
            matches.append(evidence)

        matches.sort(
            key=lambda evidence: (
                str(evidence.get("published_at") or ""),
                str(evidence.get("evidence_id") or ""),
            ),
            reverse=True,
        )
        items = []
        for evidence in matches[offset : offset + limit]:
            vm = self._evidence_vm(evidence)
            items.append(
                EvidenceSearchItemVM(
                    **vm.model_dump(),
                    claim_type=str(evidence.get("claim_type") or ""),
                    review_status=str(evidence.get("review_status") or "PENDING"),
                )
            )
        return EvidenceSearchResultVM(
            items=items,
            total=len(matches),
            offset=offset,
            limit=limit,
        )

    def evidence_facets(self) -> EvidenceFacetsVM:
        source_counts: dict[str, int] = {}
        claim_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        published_dates: list[str] = []
        for evidence in self.repo.evidence():
            source = str(evidence.get("source_id") or "")
            claim = str(evidence.get("claim_type") or "")
            status = str(evidence.get("review_status") or "PENDING")
            if source:
                source_counts[source] = source_counts.get(source, 0) + 1
            if claim:
                claim_counts[claim] = claim_counts.get(claim, 0) + 1
            status_counts[status] = status_counts.get(status, 0) + 1
            published = str(evidence.get("published_at") or "")[:10]
            if published:
                published_dates.append(published)

        def facets(counts: dict[str, int]) -> list[EvidenceFacetItemVM]:
            return [
                EvidenceFacetItemVM(value=value, count=count)
                for value, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            ]

        return EvidenceFacetsVM(
            sources=facets(source_counts),
            claim_types=facets(claim_counts),
            review_statuses=facets(status_counts),
            earliest_published_at=min(published_dates, default=""),
            latest_published_at=max(published_dates, default=""),
        )

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
        eids = change.get("evidence_ids") or []
        if not eids:
            # 空证据回退：观察窗内归一技能命中该能力域的招聘 JD（确定性，最多 3 条）
            eids = self._window_jd_evidence(change.get("skill_id", ""), ev_index)
        out = []
        for eid in eids:
            ev = ev_index.get(eid)
            if ev:
                out.append(ev)
        return out[:3]

    def _window_jd_evidence(self, skill_id: str, ev_index: dict[str, dict]) -> list[str]:
        """观察窗内提及某能力域的招聘 JD evidence_id（需存在证据记录）。"""
        if not skill_id:
            return []
        obs = self.repo.job_changeset().get("obs_window", "")
        start, _, end = obs.partition(":")
        hits: list[str] = []
        for jd_id, rec in self._jd_parsed().items():
            pub = rec.get("publish_date") or ""
            if start and end and not (start <= pub <= end):
                continue
            if not any(x.get("skill_id") == skill_id for x in rec.get("resolved") or []):
                continue
            eid = f"jd:{jd_id}"
            if eid in ev_index:
                hits.append(eid)
            if len(hits) >= 3:
                break
        return hits

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
        candidates = [
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
        ]
        candidates.extend(self._emergscan_candidates())
        return NewJobsVM(
            fixture_version="v3",
            run_id="emergscan-auto",
            candidates=candidates,
        )

    def _emergscan_candidates(self) -> list[CandidateVM]:
        """涌现扫描器（emergscan.py）候选 -> CandidateVM（确定性组装，零 LLM）。"""
        scan = self.repo.emerging_roles()
        out: list[CandidateVM] = []
        for c in scan.get("candidates", []):
            kw = c.get("keyword", "")
            total = c.get("total", 0)
            recent = c.get("recent_90d", 0)
            prior = c.get("prior_90d", 0)
            growth = c.get("growth_ratio")
            platforms = c.get("platforms", 0)
            variants = c.get("title_variants", 0)
            skills = [s["name"] for s in c.get("top_skills", []) if s.get("name")]
            samples = c.get("sample_titles", [])
            title = self._emergscan_title(kw, samples)
            growth_desc = f"增长 {growth} 倍" if growth else "从无到有"
            why = (
                f"涌现扫描检出：近 90 天 {recent} 条（前 90 天仅 {prior}，{growth_desc}），"
                f"{variants} 种标题变体、{platforms} 个平台同时涌现"
            )
            conf = self._emergscan_confidence(growth, platforms, recent)
            out.append(
                CandidateVM(
                    id=f"emerg-{kw.replace(' ', '-').lower()[:40]}",
                    title=title,
                    summary=f"{total} 条 JD · 近90天 {recent} · {growth_desc}",
                    confidence=conf,
                    companies=variants,
                    source_count=platforms,
                    status="reviewing",
                    why_new=why,
                    responsibilities=[],
                    required_skills=skills,
                    preferred_skills=[],
                    scenarios=[],
                    evidence=self._emergscan_evidence(kw),
                )
            )
        return out

    @staticmethod
    def _emergscan_title(kw: str, samples: list[str]) -> str:
        """候选展示标题：优先从样例标题取最具代表性的，回退用关键词。"""
        for t in samples:
            if kw.lower() in t.lower() and len(t) <= 60:
                return t.strip()
        return kw.title()  # 关键词首字母大写作展示标题兑底

    @staticmethod
    def _emergscan_confidence(growth: float | None, platforms: int, recent: int) -> float:
        """涌现候选置信度：增长强度 + 多平台 + 近期量的简单确定性推导。"""
        score = 0.3
        if growth is None or growth >= 10:
            score += 0.3
        elif growth >= 2:
            score += 0.2
        if platforms >= 5:
            score += 0.2
        elif platforms >= 3:
            score += 0.1
        if recent >= 50:
            score += 0.1
        elif recent >= 20:
            score += 0.05
        return round(min(score, 0.95), 2)

    def _emergscan_evidence(self, kw: str) -> list[EvidenceVM]:
        """按关键词从现有证据池筛 JD 证据（回链涌现候选的原文依据）。"""
        picks: list[dict] = []
        kw_lower = kw.lower()
        for ev in self.repo.evidence():
            if len(picks) >= 3:
                break
            payload = ev.get("payload", {})
            title = str(payload.get("title", "")).lower()
            if kw_lower in title and ev["evidence_id"].startswith("jd:"):
                picks.append(ev)
        return [self._evidence_vm(e) for e in picks]

    def _agent_evidence(self) -> list[EvidenceVM]:
        picks: list[dict] = []
        for ev in self.repo.evidence():
            if len(picks) >= 3:
                break
            if ev["evidence_id"].startswith(("jd:", "xlsx:")):
                picks.append(ev)
        return [self._evidence_vm(e) for e in picks]

    # ---------- 审核（append-only，ADR 0006） ----------

    # ---------- 岗位更新逐条审核（append-only，跨会话持久化） ----------

    @staticmethod
    def _change_review_target(job_id: str, draft: str, change_id: str) -> str:
        return f"jobchg:{job_id}:{draft}:{change_id}"

    def submit_change_review(
        self, job_id: str, draft: str, change_id: str, decision: str, note: str = ""
    ) -> dict:
        return self.submit_review(
            self._change_review_target(job_id, draft, change_id), decision, note
        )

    def change_reviews(self, job_id: str, draft: str) -> dict[str, dict]:
        """change_id -> 最新一条审核动作（同一事实日志，只取终态）。"""
        prefix = f"jobchg:{job_id}:{draft}:"
        latest: dict[str, dict] = {}
        for rec in self.repo.review_actions():
            tid = rec.get("target_id", "")
            if tid.startswith(prefix):
                latest[tid.removeprefix(prefix)] = rec
        return {
            cid: {
                "decision": rec.get("decision", ""),
                "note": rec.get("note", ""),
                "ts": rec.get("ts", ""),
            }
            for cid, rec in latest.items()
        }

    def submit_review(self, target_id: str, decision: str, note: str = "", **extra: object) -> dict:
        action = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "target_id": target_id,
            "decision": decision,
            "note": note,
            **extra,
        }
        self.repo.append_review(action)
        return {"accepted": True, **action}
