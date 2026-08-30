import { TrendInsightsWorkbench } from "@/components/trend-insights-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { buildMockJobs, type PublishedJobsView } from "@/lib/career-jobs";
import {
  loadTemporalFixture,
  loadTemporalSignalsFixture,
} from "@/lib/temporal-fixture";
import type {
  TemporalDataset,
  TemporalSignalList,
  TemporalTimeline,
} from "@/lib/temporal";

export const metadata = { title: "趋势洞察" };
export const dynamic = "force-dynamic";

const MOCK_TIMELINE: TemporalTimeline = {
  rows: [
    {
      capability_id: "cap_01",
      name: "LLM 应用",
      arxiv_onset: "2020-01",
      pypi_onset: "2023-02",
      npm_onset: "2024-12",
      report_onset: "2024-01",
      jd_onset: "2025-10",
      paper_to_jd_months: 70,
    },
    {
      capability_id: "cap_04",
      name: "AI Agent",
      arxiv_onset: "2019-01",
      pypi_onset: "2024-11",
      npm_onset: "2025-08",
      report_onset: "2025-03",
      jd_onset: "2025-09",
      paper_to_jd_months: 81,
    },
    {
      capability_id: "cap_06",
      name: "RAG / 知识库",
      arxiv_onset: "2019-05",
      pypi_onset: "2021-02",
      npm_onset: null,
      report_onset: "2025-03",
      jd_onset: "2025-11",
      paper_to_jd_months: 79,
    },
  ],
  note: "各层起始月采用首次达到规模阈值的月份。",
};

export default async function TemporalPage() {
  const [signals, temporal, timeline, jobs] = isMockMode()
    ? await Promise.all([
        loadTemporalSignalsFixture(),
        loadTemporalFixture(),
        Promise.resolve(MOCK_TIMELINE),
        Promise.resolve(buildMockJobs()),
      ])
    : await Promise.all([
        apiFetch<TemporalSignalList>("/temporal/signals", {
          timeoutMs: 30_000,
        }).then((result) => result.signals),
        apiFetch<TemporalDataset>("/temporal/dataset"),
        apiFetch<TemporalTimeline>("/temporal/timeline"),
        apiFetch<PublishedJobsView>("/jobs/published"),
      ]);
  return (
    <TrendInsightsWorkbench
      backtestRecords={temporal.backtestRecords}
      forecasts={temporal.forecasts}
      jobLabels={Object.fromEntries(
        jobs.jobs.map((job) => [job.job_id, job.title]),
      )}
      signals={signals}
      suggestions={temporal.suggestions}
      timeline={timeline}
    />
  );
}
