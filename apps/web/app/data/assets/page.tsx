import { AppShell } from "@/components/app-shell";
import { DataAssetsWorkbench } from "@/components/data-assets-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DatasetOverview } from "@/lib/datasets";

export const metadata = { title: "数据资产" };
export const dynamic = "force-dynamic";

const EMPTY: DatasetOverview = {
  total_datasets: 0,
  total_records: 0,
  ready_datasets: 0,
  pending_records: 0,
  datasets: [],
};

export default async function DataAssetsPage() {
  const overview = isMockMode()
    ? EMPTY
    : ((await apiFetch<DatasetOverview>("/datasets/overview")) ?? EMPTY);
  return (
    <AppShell>
      <DataAssetsWorkbench mockMode={isMockMode()} overview={overview} />
    </AppShell>
  );
}
