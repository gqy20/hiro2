import { AppShell } from "@/components/app-shell";
import { TasksWorkbench } from "@/components/tasks-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type {
  EvidenceFacets,
  EvidenceSearchResult,
} from "@/lib/evidence-search";
import type { ReviewTask } from "@/lib/tasks-fixture";

export const metadata = { title: "证据审核" };

export default async function TasksPage({
  searchParams,
}: Readonly<{
  searchParams: Promise<{ state?: string; view?: string; source_id?: string }>;
}>) {
  const { state, view, source_id = "" } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  if (variant === "error") {
    return (
      <AppShell>
        <FixtureState
          errorText="任务数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  }
  if (variant === "empty") {
    return (
      <AppShell>
        <FixtureState emptyText="暂无任务可领取。" state="empty" />
      </AppShell>
    );
  }
  const emptyEvidence: EvidenceSearchResult = {
    items: [],
    total: 0,
    offset: 0,
    limit: 50,
  };
  const emptyFacets: EvidenceFacets = {
    sources: [],
    claimTypes: [],
    reviewStatuses: [],
    earliestPublishedAt: "",
    latestPublishedAt: "",
  };
  const [tasks, evidence, facets] = isMockMode()
    ? [undefined, emptyEvidence, emptyFacets]
    : await Promise.all([
        apiFetch<{ tasks: ReviewTask[] }>("/tasks/my").then(
          (result) => result.tasks,
        ),
        apiFetch<EvidenceSearchResult>(
          `/evidence?limit=50${source_id ? `&source_id=${encodeURIComponent(source_id)}` : ""}`,
        ),
        apiFetch<EvidenceFacets>("/evidence/facets"),
      ]);
  return (
    <TasksWorkbench
      evidenceFacets={facets}
      initialEvidence={evidence}
      initialSource={source_id}
      initialTasks={tasks}
      initialView={view === "tasks" ? "tasks" : "evidence"}
    />
  );
}
