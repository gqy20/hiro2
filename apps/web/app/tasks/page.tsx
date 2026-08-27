import { AppShell } from "@/components/app-shell";
import { TasksWorkbench } from "@/components/tasks-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { ReviewTask } from "@/lib/tasks-fixture";

export default async function TasksPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
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
  const tasks = isMockMode()
    ? undefined
    : (await apiFetch<{ tasks: ReviewTask[] }>("/tasks/my")).tasks;
  return <TasksWorkbench initialTasks={tasks} />;
}
