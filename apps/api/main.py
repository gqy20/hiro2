"""Hiro2 API（Phase A，ADR 0006）：只读 View Model + append-only 审核。

启动：
    uv run uvicorn apps.api.main:app --port 8000
前端联调（apps/web）：
    NEXT_PUBLIC_USE_MOCK=false NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.application.diagnosis import build_diagnosis, list_candidates
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


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


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
        return build_diagnosis(candidate_id, job).model_dump()
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@app.get("/api/v1/temporal/dataset")
def temporal_dataset() -> dict:
    return build_temporal().model_dump()


@app.get("/api/v1/skills/graph")
def skills_graph(job: str = "ai-agent-v2") -> dict:
    return build_skill_graph(job).model_dump()


@app.get("/api/v1/tasks/my")
def my_tasks() -> dict:
    return build_tasks().model_dump()


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
