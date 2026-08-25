import { AppShell } from "@/components/app-shell";
import { TemporalRetrospectWorkbench } from "@/components/temporal-retrospect-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { loadTemporalFixture } from "@/lib/temporal-fixture";

export default async function TemporalRetrospectPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const fixture = await loadTemporalFixture();
  const variant =
    state === "empty" || state === "error" ? state : "ready";
  if (variant === "error") {
    return (
      <AppShell>
        <FixtureState
          errorText="回测数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  }
  if (variant === "empty") {
    return (
      <AppShell>
        <FixtureState
          emptyText="暂无回测记录。"
          state="empty"
        />
      </AppShell>
    );
  }
  return <TemporalRetrospectWorkbench backtests={fixture.backtests} />;
}