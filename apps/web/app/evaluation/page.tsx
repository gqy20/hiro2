import { AppShell } from "@/components/app-shell";
import { EvaluationWorkbench } from "@/components/evaluation-workbench";
import { FixtureState } from "@/components/workflow-ui";

export default async function EvaluationPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const variant =
    state === "empty" || state === "error" ? state : "ready";
  if (variant === "error") {
    return (
      <AppShell>
        <FixtureState
          errorText="评测数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  }
  if (variant === "empty") {
    return (
      <AppShell>
        <FixtureState
          emptyText="暂无回测运行记录。"
          state="empty"
        />
      </AppShell>
    );
  }
  return <EvaluationWorkbench />;
}