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
    skill: string;
    reason: string;
    priority: "high" | "medium";
  }>;
  pending: { title: string; description: string; href: string };
};
