import { AppShell } from "@/components/app-shell";
import { DataPipelineWorkbench } from "@/components/data-pipeline-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { PipelineRunDetail, PipelineRunList } from "@/lib/pipeline-runs";
import { loadPipelineRunsFixture } from "@/lib/pipeline-runs-fixture";

export const metadata = { title: "流水线" };

export const dynamic = "force-dynamic";

const EMPTY: PipelineRunList = { runs: [], total: 0 };

export default async function DataPipelinePage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ run_id?: string }> }>) {
  const { run_id } = await searchParams;
  const data: PipelineRunList = isMockMode()
    ? await loadPipelineRunsFixture()
    : ((await apiFetch<PipelineRunList>("/pipeline-runs?limit=50")) ?? EMPTY);

  const initialDetail =
    !isMockMode() && run_id
      ? await apiFetch<PipelineRunDetail>(
          `/pipeline-runs/${encodeURIComponent(run_id)}`,
        )
      : null;
  return (
    <AppShell>
      <DataPipelineWorkbench
        initialDetail={initialDetail}
        mockMode={isMockMode()}
        runs={data.runs}
        total={data.total}
      />
    </AppShell>
  );
}
