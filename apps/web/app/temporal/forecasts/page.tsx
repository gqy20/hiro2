import { AppShell } from "@/components/app-shell";
import { TemporalForecastsWorkbench } from "@/components/temporal-forecasts-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { loadTemporalFixture } from "@/lib/temporal-fixture";

export default async function TemporalForecastsPage({
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
          errorText="时间趋势数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  }
  if (variant === "empty") {
    return (
      <AppShell>
        <FixtureState
          emptyText="当前没有可用的预测趋势。"
          state="empty"
        />
      </AppShell>
    );
  }
  return (
    <TemporalForecastsWorkbench
      backtestRecords={fixture.backtestRecords}
      forecasts={fixture.forecasts}
    />
  );
}