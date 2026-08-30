import { TemporalSignalsWorkbench } from "@/components/temporal-signals-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadTemporalSignalsFixture } from "@/lib/temporal-fixture";
import type { TemporalSignalList } from "@/lib/temporal";

export const metadata = { title: "市场信号" };

export default async function TemporalSignalsPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const signalList: TemporalSignalList = isMockMode()
    ? await loadTemporalSignalsFixture().then((signals) => ({
        signals,
        total: signals.length,
        earliest_observed_at: signals.at(-1)?.observed_at ?? "",
        latest_observed_at: signals[0]?.observed_at ?? "",
      }))
    : await apiFetch<TemporalSignalList>("/temporal/signals", {
        timeoutMs: 30_000,
      });
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
  return <TemporalSignalsWorkbench signals={signalList.signals} />;
}
