import { AppShell } from "@/components/app-shell";
import { DataQualityWorkbench } from "@/components/data-quality-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadQualityFixture, type QualityOverview } from "@/lib/quality";

export const dynamic = "force-dynamic";

export default async function DataQualityPage() {
  const quality: QualityOverview = isMockMode()
    ? await loadQualityFixture()
    : (await apiFetch<QualityOverview>("/quality/overview")) ?? {
        source: "file",
        dataset_version: "",
        task_total: 0,
        task_resolved: 0,
        completion_rate: 0,
        dual_review_rate: null,
        avg_response_days: null,
        error_distribution: {},
        data_quality: {},
      };

  return (
    <AppShell>
      <DataQualityWorkbench quality={quality} />
    </AppShell>
  );
}
