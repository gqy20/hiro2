export type DashboardOverview = {
  source: string;
  focus: { title: string; stage: string; next: string; href: string; pending: string; summary: string };
  queue: Array<{ href: string; label: string; value: number; meta: string }>;
  status: { data_as_of: string; backtests: string; pending_reviews: string };
};
