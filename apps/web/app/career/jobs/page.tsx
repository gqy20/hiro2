import { AppShell } from "@/components/app-shell";
import { CareerJobs } from "@/components/career-jobs";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { buildMockJobs, type PublishedJobsView } from "@/lib/career-jobs";

export const metadata = { title: "目标岗位" };

export const dynamic = "force-dynamic";

export default async function CareerJobsPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  if (state === "error") {
    return (
      <AppShell>
        <FixtureState
          errorText="岗位数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  }
  if (state === "empty") {
    return (
      <AppShell>
        <FixtureState emptyText="暂无已发布岗位版本。" state="empty" />
      </AppShell>
    );
  }
  const view: PublishedJobsView = isMockMode()
    ? buildMockJobs()
    : ((await apiFetch<PublishedJobsView>("/jobs/published")) ?? {
        jobs: [],
        total: 0,
      });
  return (
    <AppShell>
      <CareerJobs view={view} />
    </AppShell>
  );
}
