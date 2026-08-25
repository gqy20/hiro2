// 时间情报相关 DTO（来自 docs/contracts.md:131-279）。
// ponytail: 不预造超出契约的字段；信号/预测/复盘/JobImpactSuggestion
// 类型直接照搬 contracts.md 形状。

export type TrendSignalEntityType =
  | "skill"
  | "technology"
  | "industry"
  | "job";
export type TrendSignalType =
  | "mention"
  | "adoption"
  | "job_requirement"
  | "release"
  | "policy";

export type TrendSignal = {
  signal_id: string;
  item_id: string;
  entity_type: TrendSignalEntityType;
  canonical_skill_id: string;
  signal_type: TrendSignalType;
  observed_at: string;
  evidence_span: string;
  confidence: number;
  evidence_ids: string[];
};

export type ForecastMode = "backtest" | "forecast";
export type ForecastDirection = "up" | "down" | "flat";

export type ForecastResult = {
  forecast_id: string;
  skill_id: string;
  mode: ForecastMode;
  as_of_date: string;
  horizon_days: number;
  current_phase: string;
  predicted_direction: ForecastDirection;
  predicted_heat: number;
  confidence: number;
  forecast_valid_until: string;
  model_version: string;
  prompt_version: string;
  rule_version: number;
  evidence_ids: string[];
};

export type BacktestRun = {
  run_id: string;
  as_of_date: string;
  horizon_days: number;
  dataset_version: string;
  forecast_ids: string[];
  ground_truth_ids: string[];
  metrics: {
    accuracy: number;
    flat_baseline_accuracy: number;
    by_predicted: Record<string, number>;
    by_actual: Record<string, number>;
    error_types: Record<string, number>;
  };
  status: "SUCCEEDED" | "FAILED" | "RUNNING";
};

export type BacktestRecord = {
  as_of: string;
  skill_id: string;
  predicted: ForecastDirection;
  actual: ForecastDirection;
  hit: boolean;
  confidence: number;
  recent: number;
  prior: number;
  rule_version: number;
};

export type JobImpactChangeType =
  | "add"
  | "remove"
  | "modify"
  | "promote"
  | "demote";
export type JobImpactReviewStatus =
  | "PENDING"
  | "ACCEPTED"
  | "MODIFIED"
  | "REJECTED";

export type JobImpactSuggestion = {
  suggestion_id: string;
  forecast_id: string;
  job_id: string;
  skill_id: string;
  change_type: JobImpactChangeType;
  suggested_level: string;
  reason: string;
  evidence_ids: string[];
  review_status: JobImpactReviewStatus;
};

export type TemporalDataset = {
  backtests: BacktestRun[];
  backtestRecords: BacktestRecord[];
  forecasts: ForecastResult[];
  signals: TrendSignal[];
  suggestions: JobImpactSuggestion[];
};

export type TemporalVariant = "ready" | "empty" | "error";