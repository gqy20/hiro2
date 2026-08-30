export type EvaluationOverview = {
  run: {
    id: string;
    algorithmVersion: string;
    datasetVersion: string;
    status: "REVIEWING";
  };
  datasets: Array<{
    id: string;
    name: string;
    samples: number;
    jobVersion: string;
  }>;
  metrics: Array<{ key: string; label: string; value: number; hint?: string }>;
  errors: Array<{
    id: string;
    code: string;
    predicted: "up" | "flat" | "down";
    actual: "up" | "flat" | "down";
    label: string;
    category: "opposite" | "missed" | "false_change" | "other";
    categoryLabel: string;
    severity: "critical" | "high" | "medium";
    count: number;
    share: number;
  }>;
  cases: Array<{
    id: string;
    asOf: string;
    skillId: string;
    skillLabel: string;
    predicted: "up" | "flat" | "down";
    actual: "up" | "flat" | "down";
    hit: boolean;
    confidence: number;
    recent: number;
    prior: number;
    ruleVersion: number;
  }>;
  summary: {
    total: number;
    hits: number;
    errors: number;
    accuracy: number;
    baselineAccuracy: number;
  };
  pending: { title: string; description: string; href: string };
};
