import type { PipelineRunList } from "@/lib/pipeline-runs";

export async function loadPipelineRunsFixture(): Promise<PipelineRunList> {
  return { runs: [], total: 0 };
}
