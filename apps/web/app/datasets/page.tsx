import { AppShell } from "@/components/app-shell";
import { DatasetWorkbench } from "@/components/dataset-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DatasetOverview } from "@/lib/datasets";

export default async function DatasetsPage() {
  const overview = isMockMode()
    ? {
        total_datasets: 0,
        total_records: 0,
        ready_datasets: 0,
        pending_records: 0,
        datasets: [],
      }
    : await apiFetch<DatasetOverview>("/datasets/overview");
  return (
    <AppShell>
      <DatasetWorkbench overview={overview} />
    </AppShell>
  );
}
