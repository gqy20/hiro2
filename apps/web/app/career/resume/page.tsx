import { AppShell } from "@/components/app-shell";
import { ResumeStudio } from "@/components/resume-studio";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { buildMockJobs, type PublishedJobsView } from "@/lib/career-jobs";

export const metadata = { title: "简历工作台" };

export const dynamic = "force-dynamic";

export default async function CareerResumePage() {
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

  return (
    <AppShell>
      <div className="page-heading">
        <h1 className="sr-only">简历工作台</h1>
        <p>
          填写结构化经历生成 PDF；右侧建议基于目标岗位的市场证据（JD
          数与技能权重）， 随目标岗位切换而变化。
        </p>
      </div>
      <ResumeStudio jobs={jobs} />
    </AppShell>
  );
}
