import { TemporalRetrospectWorkbench } from "@/components/temporal-retrospect-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadTemporalFixture } from "@/lib/temporal-fixture";
import type { TemporalDataset } from "@/lib/temporal";

async function fetchTemporalServer(): Promise<TemporalDataset> {
  if (isMockMode()) return loadTemporalFixture();
  return apiFetch<TemporalDataset>("/temporal/dataset");
}

export default async function TemporalRetrospectPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  if (variant === "error") {
    return (
      <>
        <FixtureState
          errorText="回测数据暂时不可用，请稍后重试。"
          state="error"
        />
      </>
    );
  }
  if (variant === "empty") {
    return (
      <>
        <FixtureState emptyText="暂无回测记录。" state="empty" />
      </>
    );
  }
  const data = await fetchTemporalServer();
  return <TemporalRetrospectWorkbench backtests={data.backtests} />;
}
