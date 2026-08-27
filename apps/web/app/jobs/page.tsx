import { JobUpdateWorkbench } from "@/components/job-update-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadJobUpdateFixture } from "@/lib/job-fixture";
import type { JobUpdateView } from "@/lib/api/types";

type JobUpdateVariant = "ready" | "empty" | "error";

// ponytail: RSC 页面直接处理 mock/real 切换；client 不需要这段代码，
// 因此不通过 lib/api/queries.ts（后者混入客户端 bundle 时会拉进 node:fs）。
async function fetchJobUpdateServer(
  variant: JobUpdateVariant,
): Promise<JobUpdateView> {
  if (isMockMode()) return loadJobUpdateFixture(variant);
  return apiFetch<JobUpdateView>(`/jobs/default/update?state=${variant}`);
}

export default async function JobUpdatePage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  return (
    <JobUpdateWorkbench
      fixture={await fetchJobUpdateServer(variant)}
      state={variant}
    />
  );
}
