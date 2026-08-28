import { AppShell } from "@/components/app-shell";
import { CareerJobs } from "@/components/career-jobs";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { buildMockJobs, type PublishedJobsView } from "@/lib/career-jobs";

export const dynamic = "force-dynamic";

export default async function CareerJobsPage() {
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
