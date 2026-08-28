import { AppShell } from "@/components/app-shell";
import { DataShowcase } from "@/components/data-showcase";
import { DatasetWorkbench } from "@/components/dataset-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DatasetOverview } from "@/lib/datasets";
import type { PipelineRunList } from "@/lib/pipeline-runs";
import { loadPipelineRunsFixture } from "@/lib/pipeline-runs-fixture";

export const dynamic = "force-dynamic";

const EMPTY_DATASETS: DatasetOverview = {
  total_datasets: 0,
  total_records: 0,
  ready_datasets: 0,
  pending_records: 0,
  datasets: [],
};

export default async function DataPage() {
  const overview: DatasetOverview = isMockMode()
    ? EMPTY_DATASETS
    : ((await apiFetch<DatasetOverview>("/datasets/overview")) ??
      EMPTY_DATASETS);

  const pipeline: PipelineRunList = isMockMode()
    ? await loadPipelineRunsFixture()
    : ((await apiFetch<PipelineRunList>("/pipeline-runs?limit=100")) ?? {
        runs: [],
        total: 0,
      });

  return (
    <AppShell>
      <DataShowcase overview={overview} pipeline={pipeline} />
      <DatasetWorkbench embedded overview={overview} />
    </AppShell>
  );
}
