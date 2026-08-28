export type PipelineRunStatus =
  | "PENDING"
  | "RUNNING"
  | "SUCCEEDED"
  | "FAILED"
  | "RETRYING"
  | "UNKNOWN";

export type PipelineRun = {
  run_id: string;
  component: string;
  status: string;
  stage: string;
  started_at: string;
  finished_at: string | null;
  duration_ms: number | null;
  count_summary: string;
  error: string | null;
};

export type PipelineRunList = {
  runs: PipelineRun[];
  total: number;
};
