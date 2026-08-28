import { AppShell } from "@/components/app-shell";
import { DataSourcesWorkbench } from "@/components/data-sources-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DatasetOverview } from "@/lib/datasets";

export const dynamic = "force-dynamic";

const EMPTY: DatasetOverview = {
  total_datasets: 0,
  total_records: 0,
  ready_datasets: 0,
  pending_records: 0,
  datasets: [],
};

export default async function DataSourcesPage() {
  const overview: DatasetOverview = isMockMode()
    ? EMPTY
    : (await apiFetch<DatasetOverview>("/datasets/overview")) ?? EMPTY;

  return (
    <AppShell>
      <DataSourcesWorkbench overview={overview} />
    </AppShell>
  );
}
