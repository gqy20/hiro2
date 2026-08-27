export type DashboardOverview = {
  source: string;
  focus: {
    title: string;
    stage: string;
    next: string;
    href: string;
    pending: string;
    summary: string;
  };
  queue: Array<{ href: string; label: string; value: number; meta: string }>;
  status: { data_as_of: string; backtests: string; pending_reviews: string };
  jobs: Array<{
    title: string;
    version: string;
    status: string;
    pending: number;
    href: string;
  }>;
  activities: Array<{ label: string; detail: string }>;
  metrics: {
    positions: number;
    needs_update: number;
    pending_changes: number;
    published_versions: number;
  };
  trends: Array<{
    skill_id: string;
    label: string;
    months: string[];
    values: number[];
    sample_counts: number[];
  }>;
  attention: Array<{ title: string; detail: string; href: string }>;
};
