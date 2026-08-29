import { NewJobsWorkbench } from "@/components/new-jobs-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadNewJobsFixture } from "@/lib/new-jobs-fixture";
import type { NewJobsView } from "@/lib/api/types";

export const metadata = { title: "岗位发现" };

type NewJobsVariant = "ready" | "empty" | "error";

// ponytail: RSC 页面直接处理 mock/real 切换（与 jobs 页同一模式），
// 不通过 lib/api/queries.ts，避免 node:fs 进入客户端 bundle。
async function fetchNewJobsServer(
  variant: NewJobsVariant,
): Promise<NewJobsView> {
  if (isMockMode()) return loadNewJobsFixture(variant);
  if (variant !== "ready") return loadNewJobsFixture(variant); // empty/error 边界态保留 fixture 联调
  return apiFetch<NewJobsView>("/emerging-jobs");
}

export default async function NewJobsPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  return (
    <NewJobsWorkbench
      fixture={await fetchNewJobsServer(variant)}
      state={variant}
    />
  );
}
