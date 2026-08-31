import { AppShell } from "@/components/app-shell";
import { ResumeStudio } from "@/components/resume-studio";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { buildMockJobs, type PublishedJobsView } from "@/lib/career-jobs";
import { loadDiagnosisFixture } from "@/lib/diagnosis-fixture";
import type { DiagnosisFixture } from "@/lib/diagnosis";
import {
  buildMockAdvice,
  emptyDraft,
  type AdviceView,
  type ResumeDraftInput,
} from "@/lib/resume-studio";

export const metadata = { title: "简历工作台" };

export const dynamic = "force-dynamic";

export default async function CareerResumePage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ job?: string }> }>) {
  const { job: requestedJob } = await searchParams;
  let view: PublishedJobsView = buildMockJobs();
  if (!isMockMode()) {
    try {
      view = await apiFetch<PublishedJobsView>("/jobs/published", {
        timeoutMs: 10000,
      });
    } catch {
      // 岗位列表加载失败时仍可用 mock 列表进入工作台
    }
  }
  const jobs = view.jobs.map((j) => ({
    version_id: j.version_id,
    title: j.title,
  }));
  const initialJobId =
    jobs.find((job) => job.version_id === requestedJob)?.version_id ??
    jobs.find((job) => job.version_id === "ai-agent-v2")?.version_id ??
    jobs[0]?.version_id ??
    "";
  const initialJobTitle =
    jobs.find((job) => job.version_id === initialJobId)?.title ?? "目标岗位";
  const fixture: DiagnosisFixture = isMockMode()
    ? await loadDiagnosisFixture()
    : await apiFetch<DiagnosisFixture>(
        `/diagnosis/synth_agent_senior_02${
          initialJobId ? `?job=${encodeURIComponent(initialJobId)}` : ""
        }`,
      );
  const initialDraft: ResumeDraftInput = {
    ...emptyDraft(),
    name: fixture.candidate.name,
    title: initialJobTitle,
    summary: `${fixture.candidate.headline}，目标岗位为${initialJobTitle}。`,
    skills: fixture.candidate.skills
      .filter((skill) => skill.status !== "missing")
      .map((skill) => skill.name),
    projects: fixture.candidate.projects.map((project) => ({
      name: project.text,
      desc: "能力证明",
      bullets: [""],
    })),
  };
  let initialAdvice: AdviceView | null = isMockMode()
    ? buildMockAdvice(initialJobTitle)
    : null;
  if (!isMockMode() && initialJobId) {
    try {
      initialAdvice = await apiFetch<AdviceView>(
        `/career/resume/advice?job_version_id=${encodeURIComponent(initialJobId)}`,
        { method: "POST", body: initialDraft, timeoutMs: 20000 },
      );
    } catch {
      initialAdvice = null;
    }
  }

  return (
    <AppShell>
      <ResumeStudio
        initialAdvice={initialAdvice}
        initialDraft={initialDraft}
        initialJobId={initialJobId}
        jobs={jobs}
      />
    </AppShell>
  );
}
