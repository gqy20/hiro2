import { SkillsWorkbench } from "@/components/skills-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { buildMockJobs } from "@/lib/career-jobs";
import { loadSkillFixture, loadSkillFixtureForJob } from "@/lib/skill-fixture";
import type { PublishedJobsView, PublishedJob } from "@/lib/career-jobs";
import type { SkillGraphView } from "@/lib/api/types";

type SkillGraphVariant = "ready" | "empty" | "error";

const DEFAULT_JOB = "ai-agent-v2";

// ponytail: RSC 页面直接处理 mock/real 切换，不通过 lib/api/queries.ts，
// 避免 node:fs/promises 被拉进客户端 bundle。
async function fetchSkillServer(
  variant: SkillGraphVariant,
  job: string,
): Promise<SkillGraphView> {
  if (isMockMode()) {
    if (variant === "ready" && job !== DEFAULT_JOB) {
      const fixture = await loadSkillFixtureForJob(job);
      if (fixture) return fixture;
    }
    return loadSkillFixture(variant);
  }
  return apiFetch<SkillGraphView>(
    `/skills/graph?job=${encodeURIComponent(job)}`,
  );
}

async function fetchJobsServer(): Promise<PublishedJob[]> {
  if (isMockMode()) return buildMockJobs().jobs;
  try {
    const view = await apiFetch<PublishedJobsView>("/jobs/published");
    return view.jobs;
  } catch {
    return []; // 岗位列表失败不阻塞图谱渲染，选择器退化为当前岗位
  }
}

export default async function SkillsPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string; job?: string }> }>) {
  const { state, job } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  const jobVersionId = job || DEFAULT_JOB;
  const [fixture, jobs] = await Promise.all([
    fetchSkillServer(variant, jobVersionId),
    fetchJobsServer(),
  ]);
  return (
    <SkillsWorkbench
      key={jobVersionId}
      fixture={fixture}
      jobs={jobs}
      jobVersionId={jobVersionId}
      state={variant}
    />
  );
}
