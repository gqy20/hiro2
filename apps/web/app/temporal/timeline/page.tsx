import { TemporalTimelineWorkbench } from "@/components/temporal-timeline-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { TemporalTimeline } from "@/lib/temporal";

export const metadata = { title: "技术传导" };

const MOCK: TemporalTimeline = {
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
  note: "各层起始月 = 首次达到阈值的月份（论文 3 篇 / 包份额 / 日报 3 次 / JD 2 次）",
};

export default async function TimelinePage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  if (state === "error") {
    return (
      <FixtureState
        errorText="时间轴数据暂时不可用，请稍后重试。"
        state="error"
      />
    );
  }
  const data = isMockMode()
    ? MOCK
    : await apiFetch<TemporalTimeline>("/temporal/timeline");

  if (state === "empty" || data.rows.length === 0) {
    return <FixtureState emptyText="暂无可用的技术传导数据。" state="empty" />;
  }
  return <TemporalTimelineWorkbench data={data} />;
}
