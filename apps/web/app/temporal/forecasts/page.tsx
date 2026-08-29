import { TemporalForecastsWorkbench } from "@/components/temporal-forecasts-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { loadTemporalFixture } from "@/lib/temporal-fixture";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { TemporalDataset } from "@/lib/temporal";

export const metadata = { title: "趋势预测" };

export default async function TemporalForecastsPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const fixture = isMockMode()
    ? await loadTemporalFixture()
    : await apiFetch<TemporalDataset>("/temporal/dataset");
  const variant = state === "empty" || state === "error" ? state : "ready";
  if (variant === "error") {
    return (
      <>
        <FixtureState
          errorText="时间趋势数据暂时不可用，请稍后重试。"
          state="error"
        />
      </>
    );
  }
  if (variant === "empty") {
    return (
      <>
        <FixtureState emptyText="当前没有可用的预测趋势。" state="empty" />
      </>
    );
  }
  return (
    <TemporalForecastsWorkbench
      backtestRecords={fixture.backtestRecords}
      forecasts={fixture.forecasts}
    />
  );
}
