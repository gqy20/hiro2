"""Hiro2 API（Phase A，ADR 0006）：只读 View Model + append-only 审核。

启动：
    uv run uvicorn apps.api.main:app --port 8000
前端联调（apps/web）：
    NEXT_PUBLIC_USE_MOCK=false NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.application.career import add_proof, save_growth_task, save_profile, set_active_target
from backend.application.dashboard import build_dashboard
from backend.application.diagnosis import build_diagnosis, list_candidates
from backend.application.evaluation import build_evaluation_overview
from backend.application.quality import build_quality_overview
from backend.application.service import ApplicationService
from backend.application.temporal_vm import build_skill_graph, build_tasks, build_temporal
from backend.application.training import build_training_output

app = FastAPI(title="Hiro2 API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
svc = ApplicationService()


class ReviewRequest(BaseModel):
    decision: str = Field(pattern="^(accepted|rejected|needs_evidence|modified)$")
    note: str = ""


class GrowthTaskRequest(BaseModel):
    completed: bool


class ProofRequest(BaseModel):
    skill_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=1000)
    proof_url: str | None = Field(default=None, max_length=500)


class TargetRequest(BaseModel):
    job_version_id: str = Field(min_length=1, max_length=120)


class ProfileSkillRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    status: str = Field(pattern="^(ready|partial|missing)$")


class ProfileRequest(BaseModel):
    skills: list[ProfileSkillRequest] = Field(default_factory=list, max_length=60)
    projects: list[str] = Field(default_factory=list, max_length=10)


def _health_status() -> dict:
    postgres = "not_configured"
    database_url = os.getenv("DATABASE_URL", "")
    if database_url:
        try:
            import psycopg

            with psycopg.connect(database_url, connect_timeout=2):
                postgres = "ok"
        except Exception:
            postgres = "unavailable"

    neo4j = "not_configured"
    if os.getenv("NEO4J_URI"):
        try:
            from backend.infra.neo4j import check_neo4j

            neo4j = "ok" if check_neo4j() else "unavailable"
        except Exception:
            neo4j = "unavailable"

    required = [postgres] if database_url else []
    status = "ok" if all(x == "ok" for x in required) else "degraded"
    return {"status": status, "postgres": postgres, "neo4j": neo4j}


@app.get("/health/live")
def health_live() -> dict:
    """Process liveness; does not require external dependencies."""
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready(response: Response) -> dict:
    """Readiness; PostgreSQL is required when configured, Neo4j is degradable."""
    result = _health_status()
    if result["status"] != "ok":
        response.status_code = 503
    return result


@app.get("/health")
def health(response: Response) -> dict:
    """Backward-compatible alias for readiness checks."""
    return health_ready(response)


@app.get("/api/v1/jobs/default/update")
def job_update(state: str = "ready") -> dict:
    if state not in ("ready", "empty", "error"):
        raise HTTPException(400, "state 只支持 ready/empty/error")
    if state == "error":
        raise HTTPException(503, "模拟错误态（前端 error 边界联调）")
    return svc.job_update(state).model_dump(by_alias=True)


@app.get("/api/v1/emerging-jobs")
def emerging_jobs() -> dict:
    return svc.emerging_jobs().model_dump(by_alias=True)


@app.get("/api/v1/dashboard/overview")
def dashboard_overview() -> dict:
    return build_dashboard().model_dump()


@app.get("/api/v1/evaluation/overview")
def evaluation_overview() -> dict:
    return build_evaluation_overview()


@app.get("/api/v1/emerging-jobs/{candidate_id}/review")
def emerging_review_get(candidate_id: str) -> dict:
    data = svc.emerging_jobs().model_dump(by_alias=True)
    for c in data["candidates"]:
        if c["id"] == candidate_id:
            return c
    raise HTTPException(404, f"候选不存在: {candidate_id}")


@app.post("/api/v1/emerging-jobs/{candidate_id}/review")
def emerging_review(candidate_id: str, req: ReviewRequest) -> dict:
    return svc.submit_review(candidate_id, req.decision, req.note)


@app.get("/api/v1/evidence/{evidence_id}")
def evidence(evidence_id: str) -> dict:
    vm = svc.evidence_by_id(evidence_id)
    if vm is None:
        raise HTTPException(404, f"证据不存在: {evidence_id}")
    return vm.model_dump(by_alias=True)


@app.get("/api/v1/candidates")
def candidates() -> list[dict]:
    return list_candidates()


@app.get("/api/v1/diagnosis/{candidate_id}")
def diagnosis(candidate_id: str, job: str = "ai-agent-v2") -> dict:
    try:
        return build_diagnosis(candidate_id, job).model_dump(by_alias=True)
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.put("/api/v1/candidates/{candidate_id}/growth-tasks/{skill_id}")
def update_growth_task(
    candidate_id: str, skill_id: str, req: GrowthTaskRequest, job: str = "ai-agent-v2"
) -> dict:
    try:
        return save_growth_task(candidate_id, job, skill_id, req.completed)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.post("/api/v1/candidates/{candidate_id}/proofs")
def create_proof(candidate_id: str, req: ProofRequest) -> dict:
    try:
        return add_proof(candidate_id, req.skill_id, req.title, req.description, req.proof_url)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.put("/api/v1/candidates/{candidate_id}/target")
def update_target(candidate_id: str, req: TargetRequest) -> dict:
    try:
        return set_active_target(candidate_id, req.job_version_id)
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.patch("/api/v1/candidates/{candidate_id}/profile")
def update_profile(candidate_id: str, req: ProfileRequest) -> dict:
    try:
        return save_profile(
            candidate_id,
            [skill.model_dump() for skill in req.skills],
            req.projects,
        )
    except LookupError as exc:
        raise HTTPException(404, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc


@app.get("/api/v1/temporal/dataset")
def temporal_dataset() -> dict:
    return build_temporal().model_dump()


@app.get("/api/v1/skills/graph")
def skills_graph(job: str = "ai-agent-v2") -> dict:
    graph = build_skill_graph(job)
    if os.getenv("NEO4J_URI"):
        try:
            from backend.infra.neo4j import read_job_graph

            nodes, _ = read_job_graph(job)
            if nodes:
                # Neo4j 投影校准 role；VM 节点的别名/位置/关联版本/信号等字段保留
                roles = {n["id"]: n["role"] for n in nodes if n["id"] != "root"}
                graph = graph.model_copy(
                    update={
                        "nodes": [
                            n.model_copy(update={"role": roles[n.id]}) if n.id in roles else n
                            for n in graph.nodes
                        ]
                    }
                )
        except Exception:
            pass
    raw = graph.model_dump()
    return {
        "fixtureVersion": raw["fixture_version"],
        "mode": raw["mode"],
        "run": {
            "id": raw["run"].get("id", ""),
            "datasetVersion": raw["run"].get("datasetVersion", ""),
            "status": raw["run"].get("status", "REVIEWING"),
        },
        "context": {
            "jobTitle": raw["context"].get("jobTitle", ""),
            "baselineVersion": raw["context"].get("baselineVersion", ""),
            "targetVersion": raw["context"].get("targetVersion", ""),
            "timeWindow": raw["context"].get("timeWindow", ""),
        },
        "nodes": [
            {
                "id": node["id"],
                "label": node["label"],
                "capabilityId": node["capability_id"],
                "pointName": node["point_name"],
                "role": node["role"],
                "status": node["status"],
                "aliases": node["aliases"],
                "evidenceIds": node["evidence_ids"],
                "position": node["position"],
                "techStack": node["tech_stack"],
                "jobVersions": [
                    {
                        "versionId": ref["version_id"],
                        "title": ref["title"],
                        "role": ref["role"],
                        "weight": ref["weight"],
                    }
                    for ref in node["job_versions"]
                ],
                "signal": {
                    "jdMentions": node["signal"].get("jd_mentions", 0),
                    "mentionShare": node["signal"].get("mention_share", 0),
                }
                if node["signal"]
                else None,
            }
            for node in raw["nodes"]
        ],
        "edges": raw["edges"],
        "filterOptions": {
            "techStacks": raw["filter_options"].get("techStacks", []),
            "roles": raw["filter_options"].get("roles", []),
            "capabilityTypes": raw["filter_options"].get("capabilityTypes", []),
        },
    }


@app.get("/api/v1/tasks/my")
def my_tasks() -> dict:
    return build_tasks().model_dump()


@app.get("/api/v1/quality/overview")
def quality_overview() -> dict:
    return build_quality_overview(os.getenv("DATABASE_URL") or None).model_dump()


@app.get("/api/v1/jobs/{job_version_id}/training-output")
def training_output(job_version_id: str) -> dict:
    """F-T3.6：岗位标准下游输出——JD 模板 / 培养任务 / 能力证明要求。"""
    try:
        return build_training_output(job_version_id).model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.post("/api/v1/candidates/resumes")
async def upload_resume(file: UploadFile) -> dict:
    """F-T3.4：上传 PDF/DOCX -> LLM 抽取 -> 双层归一 -> 候选人画像。"""
    import tempfile

    from backend.candidates.parse import (
        ResumeRawExtraction,
        build_profile,
        llm_resolve_unmatched,
        parse_document,
    )
    from backend.skills.resolver import load_resolver

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in (".pdf", ".docx", ".txt", ".md"):
        raise HTTPException(400, f"不支持的格式 {suffix}，请上传 PDF/DOCX/TXT")

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        text = parse_document(tmp_path)
        if not text.strip():
            raise HTTPException(422, "解析结果为空，请检查文件内容")
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    # LLM 抽取 + 双层归一（endpoint 本身是 async，直接 await）
    from scripts.candmatch import _extract

    raw = await _extract(text)
    extraction = ResumeRawExtraction.model_validate(raw)
    resolver = load_resolver()
    profile = build_profile("upload_pending", extraction, resolver)

    # LLM 归层
    unresolved = [s.mention for s in profile.skills if not s.skill_id]
    cands: dict = {}
    if unresolved:
        cands = await llm_resolve_unmatched(unresolved, text[:400])
        for s in profile.skills:
            if s.skill_id or s.mention not in cands:
                continue
            c = cands[s.mention]
            if c.is_skill and c.capability_id and c.confidence >= 0.6:
                s.skill_id = c.capability_id
                s.resolved_by = "llm"
                s.reason = c.reason
            else:
                s.resolved_by = "unmatched"

    return {
        "rawText": text[:2000],
        "profile": profile.model_dump(),
        "stats": {
            "totalSkills": len(profile.skills),
            "resolved": sum(1 for s in profile.skills if s.skill_id),
            "byDict": sum(1 for s in profile.skills if s.resolved_by == "dict"),
            "byLlm": sum(1 for s in profile.skills if s.resolved_by == "llm"),
            "unresolved": sum(1 for s in profile.skills if s.resolved_by == "unmatched"),
        },
    }
