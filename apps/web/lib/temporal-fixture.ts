import { readFile } from "node:fs/promises";
import path from "node:path";

import type {
  BacktestRecord,
  BacktestRun,
  ForecastDirection,
  ForecastResult,
  JobImpactChangeType,
  JobImpactSuggestion,
  TemporalDataset,
  TrendSignal,
} from "@/lib/temporal";

const baseDir = path.resolve(process.cwd(), "../../data/processed/wechat-mp");

type RawBacktest = {
  metrics: {
    horizon_days: number;
    as_of_points: string[];
    predictions: number;
    hits: number;
    accuracy: number;
    flat_baseline_accuracy: number;
    by_predicted: Record<string, number>;
    by_actual: Record<string, number>;
    error_types: Record<string, number>;
    rule_version: number;
  };
  records: BacktestRecord[];
};

type RawEvent = {
  event_id: string;
  item_id: string;
  event_type: string;
  title: string;
  summary?: string;
  entities?: string[];
  fact_grade?: string;
  urls?: string[];
  skill_mentions?: string[];
  prompt_version?: string;
  model_version?: string;
  published_at?: string;
  observed_at?: string;
};

function toDirection(value: string | undefined): ForecastDirection {
  if (value === "up" || value === "down") return value;
  return "flat";
}

function readJson<T>(file: string): Promise<T> {
  return readFile(path.join(baseDir, file), "utf8").then(
    (s) => JSON.parse(s) as T,
  );
}

async function readEvents(): Promise<RawEvent[]> {
  const content = await readFile(path.join(baseDir, "events.jsonl"), "utf8");
  return content
    .split("\n")
    .filter((line) => line.trim().length > 0)
    .map((line) => JSON.parse(line) as RawEvent);
}

/** 读取 sigbuild 信号；通用聚合只带近 90 天，信号页显式请求完整历史。 */
async function loadSignals(completeHistory = false): Promise<TrendSignal[]> {
  const signalsDir = path.resolve(
    process.cwd(),
    "../../data/processed/temporal",
  );
  try {
    const content = await readFile(
      path.join(signalsDir, "signals.jsonl"),
      "utf8",
    );
    const signals = content
      .split("\n")
      .filter((line) => line.trim().length > 0)
      .map((line) => JSON.parse(line) as TrendSignal)
      .sort((a, b) => b.observed_at.localeCompare(a.observed_at));
    if (completeHistory) return signals;
    const cutoff = Date.now() - 90 * 24 * 3600 * 1000;
    return signals
      .filter((signal) => Date.parse(signal.observed_at) >= cutoff)
      .slice(0, 2000);
  } catch {
    return [];
  }
}

export function loadTemporalSignalsFixture(): Promise<TrendSignal[]> {
  return loadSignals(true);
}

export async function loadTemporalFixture(): Promise<TemporalDataset> {
  const [h30, h60, h90, events] = await Promise.all([
    readJson<RawBacktest>("backtest-h30.json"),
    readJson<RawBacktest>("backtest-h60.json"),
    readJson<RawBacktest>("backtest-h90.json"),
    readEvents(),
  ]);

  const backtests: BacktestRun[] = [h30, h60, h90].map((raw) => ({
    run_id: `BT-${raw.metrics.horizon_days}-${raw.metrics.rule_version}`,
    as_of_date: raw.metrics.as_of_points.at(-1) ?? "2026-07-01",
    horizon_days: raw.metrics.horizon_days,
    dataset_version: "wechat-mp-2026-07",
    forecast_ids: [],
    ground_truth_ids: [],
    metrics: {
      accuracy: raw.metrics.accuracy,
      flat_baseline_accuracy: raw.metrics.flat_baseline_accuracy,
      by_predicted: raw.metrics.by_predicted,
      by_actual: raw.metrics.by_actual,
      error_types: raw.metrics.error_types,
    },
    status: "SUCCEEDED",
  }));

  // 预测：取 h30 末次 as_of 的 top 5 skill
  const lastAsOf = h30.metrics.as_of_points.at(-1) ?? "2026-07-01";
  const recordsAtLast = h30.records.filter((r) => r.as_of === lastAsOf);
  const topSkills = recordsAtLast.slice(0, 5);

  const forecasts: ForecastResult[] = topSkills.map((rec, idx) => ({
    forecast_id: `FCT-${rec.skill_id}-h30-${idx}`,
    skill_id: rec.skill_id,
    mode: "forecast" as const,
    as_of_date: lastAsOf,
    horizon_days: 30,
    current_phase:
      rec.predicted === "up"
        ? "上升期"
        : rec.predicted === "down"
          ? "下降期"
          : "平稳期",
    predicted_direction: rec.predicted,
    predicted_heat: rec.recent,
    confidence: rec.confidence,
    forecast_valid_until: "2026-08-01",
    model_version: "temporal-v1",
    prompt_version: "report-event-v3",
    rule_version: 1,
    evidence_ids: events
      .filter((e) => e.skill_mentions?.includes(rec.skill_id))
      .slice(0, 3)
      .map((e) => e.event_id),
  }));

  // 聚合 fixture 只携带近 90 天信号；完整历史由信号页专用入口读取
  const signals: TrendSignal[] = await loadSignals();

  // 建议：从前 3 个 forecast 各派生一个
  const suggestions: JobImpactSuggestion[] = forecasts.slice(0, 3).map((f) => {
    const changeType: JobImpactChangeType =
      f.predicted_direction === "up"
        ? "add"
        : f.predicted_direction === "down"
          ? "remove"
          : "modify";
    return {
      suggestion_id: `JIS-${f.skill_id}`,
      forecast_id: f.forecast_id,
      job_id: "ai-app-engineer-v1.5",
      skill_id: f.skill_id,
      change_type: changeType,
      suggested_level:
        f.predicted_direction === "up"
          ? "required"
          : f.predicted_direction === "down"
            ? "out_of_scope"
            : "preferred",
      reason: `${f.skill_id} ${toDirection(f.predicted_direction)}于 ${f.as_of_date}，置信度 ${(f.confidence * 100).toFixed(0)}%`,
      evidence_ids: f.evidence_ids,
      review_status: "PENDING",
    };
  });

  return {
    backtests,
    backtestRecords: h30.records,
    forecasts,
    signals,
    suggestions,
  };
}
