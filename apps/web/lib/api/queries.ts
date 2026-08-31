// 客户端可调用的查询函数。RSC 页面不通过本文件读取数据（避免把
// node:fs 路径拉进客户端 bundle）；RSC 直接调用 loadXxxFixture 或 apiFetch。
//
// 客户端 mutation（publishJobVersion、逐条审核等）按相同模式增量添加。

import { apiFetch, isMockMode } from "@/lib/api/client";

export type PublishResult = {
  versionId: string;
  publishedAt: string;
  reviewActionIds: string[];
};

export async function saveCandidateTarget(
  candidateId: string,
  jobVersionId: string,
) {
  if (isMockMode()) return { candidateId, jobVersionId, isActive: true };
  return apiFetch(`/candidates/${encodeURIComponent(candidateId)}/target`, {
    method: "PUT",
    body: { job_version_id: jobVersionId },
  });
}

export async function saveCandidateProfile(
  candidateId: string,
  skills: Array<{
    name: string;
    status: string;
    level: string;
    years: number | null;
  }>,
  projects: string[],
) {
  if (isMockMode())
    return {
      profileVersion: "session",
      matchId: "mock-match",
      overallScore: 0,
    };
  return apiFetch(`/candidates/${encodeURIComponent(candidateId)}/profile`, {
    method: "PATCH",
    body: { skills, projects },
  });
}

export async function addCandidateProof(
  candidateId: string,
  proof: {
    skillId: string;
    title: string;
    description: string;
    proofUrl?: string;
  },
) {
  if (isMockMode()) {
    return { proofId: Date.now(), createdAt: new Date().toISOString() };
  }
  return apiFetch(`/candidates/${encodeURIComponent(candidateId)}/proofs`, {
    method: "POST",
    body: {
      skill_id: proof.skillId,
      title: proof.title,
      description: proof.description,
      proof_url: proof.proofUrl || null,
    },
  });
}

// ponytail: mock 模式无副作用 + 1.4s 模拟延迟，real 模式 POST。
export async function publishJobVersion(
  jobId: string,
  version: string,
): Promise<PublishResult> {
  if (isMockMode()) {
    await new Promise((resolve) => setTimeout(resolve, 1400));
    return {
      versionId: `${jobId}:${version}`,
      publishedAt: new Date().toISOString().slice(0, 10),
      reviewActionIds: [],
    };
  }
  return apiFetch<PublishResult>(
    `/jobs/${encodeURIComponent(jobId)}/versions/${encodeURIComponent(version)}/publish`,
    { method: "POST", body: { jobId, version } },
  );
}

export type EmergingReviewDecision = "accepted" | "rejected";

// 新岗位候选审核：real 模式 POST 后端留痕（append-only review-actions）。
export async function reviewEmergingJob(
  candidateId: string,
  decision: EmergingReviewDecision,
  note = "",
): Promise<{ accepted: boolean }> {
  if (isMockMode()) {
    await new Promise((resolve) => setTimeout(resolve, 600));
    return { accepted: true };
  }
  return apiFetch<{ accepted: boolean }>(
    `/emerging-jobs/${encodeURIComponent(candidateId)}/review`,
    { method: "POST", body: { decision, note } },
  );
}

export type ChangeReviewDecision =
  "accepted" | "rejected" | "needs_evidence" | "modified";

export type ChangeReviewRecord = {
  decision: ChangeReviewDecision;
  note: string;
  ts: string;
};

// 岗位更新逐条审核：读取某草稿的审核终态（real 走后端；mock 无持久状态）。
export async function fetchChangeReviews(
  jobId: string,
  draft: string,
): Promise<Record<string, ChangeReviewRecord>> {
  if (isMockMode()) return {};
  try {
    const data = await apiFetch<{
      reviews: Record<string, ChangeReviewRecord>;
    }>(
      `/jobs/${encodeURIComponent(jobId)}/updates/reviews?draft=${encodeURIComponent(draft)}`,
    );
    return data.reviews;
  } catch {
    return {}; // 读取失败不阻断页面，退化为会话内状态
  }
}

// 岗位更新逐条审核：提交决策留痕（append-only），note 可携带编辑后的说明。
export async function submitChangeReview(
  jobId: string,
  draft: string,
  changeId: string,
  decision: ChangeReviewDecision,
  note = "",
): Promise<{ accepted: boolean }> {
  if (isMockMode()) {
    await new Promise((resolve) => setTimeout(resolve, 120));
    return { accepted: true };
  }
  return apiFetch<{ accepted: boolean }>(
    `/jobs/${encodeURIComponent(jobId)}/updates/review`,
    {
      method: "POST",
      body: { draft, change_id: changeId, decision, note },
    },
  );
}
