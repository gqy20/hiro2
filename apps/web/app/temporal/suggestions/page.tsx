import { TemporalSuggestionsWorkbench } from "@/components/temporal-suggestions-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadTemporalFixture } from "@/lib/temporal-fixture";
import type { TemporalDataset } from "@/lib/temporal";

export const metadata = { title: "岗位影响" };

export default async function TemporalSuggestionsPage({
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
          errorText="影响建议数据暂时不可用，请稍后重试。"
          state="error"
        />
      </>
    );
  }
  if (variant === "empty") {
    return (
      <>
        <FixtureState emptyText="暂无影响建议。" state="empty" />
      </>
    );
  }
  return <TemporalSuggestionsWorkbench initial={fixture.suggestions} />;
}
