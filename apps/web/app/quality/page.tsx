import { AppShell } from "@/components/app-shell";
import { QualityWorkbench } from "@/components/quality-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { loadTemporalFixture } from "@/lib/temporal-fixture";
import { loadQualityFixture, type QualityOverview } from "@/lib/quality";
import { apiFetch, isMockMode } from "@/lib/api/client";

export default async function QualityPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const variant =
    state === "empty" || state === "error" ? state : "ready";
  if (variant === "error") {
    return (
      <AppShell>
        <FixtureState
          errorText="质量看板数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  }
  if (variant === "empty") {
    return (
      <AppShell>
        <FixtureState
          emptyText="暂无回测 / 审核记录。"
          state="empty"
        />
      </AppShell>
    );
  }
  const temporal = await loadTemporalFixture();
  const quality = isMockMode()
    ? await loadQualityFixture()
    : await apiFetch<QualityOverview>("/api/v1/quality/overview");
  return <QualityWorkbench temporal={temporal} quality={quality} />;
}
