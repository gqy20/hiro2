export type PipelineRunStatus =
  "PENDING" | "RUNNING" | "SUCCEEDED" | "FAILED" | "RETRYING" | "UNKNOWN";

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

export type PipelineRunDetail = {
  run: PipelineRun;
  config: Record<string, unknown>;
  metrics: Record<string, unknown>;
  events: Array<Record<string, unknown>>;
  event_count: number;
  artifacts: Array<{ name: string; size: number }>;
};
