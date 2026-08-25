"""Hiro2 API（Phase A，ADR 0006）：只读 View Model + append-only 审核。

启动：
    uv run uvicorn apps.api.main:app --port 8000
前端联调（apps/web）：
    NEXT_PUBLIC_USE_MOCK=false NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
"""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.application.service import ApplicationService

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
