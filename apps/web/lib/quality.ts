import { readFile } from "node:fs/promises";
import path from "node:path";

export type QualityOverview = {
  source: "postgres" | "file";
  dataset_version: string;
  task_total: number;
  task_resolved: number;
  completion_rate: number;
  dual_review_rate: number | null;
  avg_response_days: number | null;
  error_distribution: Record<string, number>;
  data_quality: Record<string, string>;
};

const samplesDir = path.resolve(process.cwd(), "../../evaluation/samples");

export async function loadQualityFixture(): Promise<QualityOverview> {
  const manifest = JSON.parse(
    await readFile(path.join(samplesDir, "manifest.json"), "utf8"),
  ) as {
    dataset_version?: string;
    role?: { n?: number };
    domain?: { n?: number };
    event?: { n?: number };
  };
  const metrics = JSON.parse(
    await readFile(path.join(samplesDir, "metrics.json"), "utf8"),
  ) as Record<string, { labeled?: number }>;
  const total = [manifest.role, manifest.domain, manifest.event].reduce(
    (sum, item) => sum + (item?.n ?? 0),
    0,
  );
  const resolved = ["role_mapping", "domain_judgment", "event_extraction"].reduce(
    (sum, key) => sum + (metrics[key]?.labeled ?? 0),
    0,
  );
  return {
    source: "file",
    dataset_version: manifest.dataset_version ?? "",
    task_total: total,
    task_resolved: resolved,
    completion_rate: total ? Number((resolved / total).toFixed(3)) : 0,
    dual_review_rate: null,
    avg_response_days: null,
    error_distribution: {},
    data_quality: {
      completion: total ? "available" : "unavailable",
      dual_review: "unavailable",
      response_time: "unavailable",
      errors: "unavailable",
    },
  };
}
