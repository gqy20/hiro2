import { TemporalSignalsWorkbench } from "@/components/temporal-signals-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadTemporalFixture } from "@/lib/temporal-fixture";
import type { TemporalDataset } from "@/lib/temporal";

export const metadata = { title: "市场信号" };

export default async function TemporalSignalsPage({
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
          errorText="时间信号数据暂时不可用，请稍后重试。"
          state="error"
        />
      </>
    );
  }
  if (variant === "empty") {
    return (
      <>
        <FixtureState emptyText="当前时间窗内暂无信号。" state="empty" />
      </>
    );
  }
  return <TemporalSignalsWorkbench signals={fixture.signals} />;
}
