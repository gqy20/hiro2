// 四层时间轴：论文 arXiv -> PyPI/npm 包 -> 日报 -> JD 的技术传导（只读）。

import { AppShell } from "@/components/app-shell";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";

type TimelineRow = {
  capabilityId: string;
  name: string;
  arxivOnset: string | null;
  pypiOnset: string | null;
  npmOnset: string | null;
  reportOnset: string | null;
  jdOnset: string | null;
  paperToJdMonths: number | null;
};

type Timeline = { rows: TimelineRow[]; note: string };

const MOCK: Timeline = {
  rows: [
    {
      capabilityId: "cap_01",
      name: "LLM应用",
      arxivOnset: "2020-01",
      pypiOnset: "2023-02",
      npmOnset: "2024-12",
      reportOnset: "2024-01",
      jdOnset: "2025-10",
      paperToJdMonths: 70,
    },
    {
      capabilityId: "cap_04",
      name: "AI Agent",
      arxivOnset: "2019-01",
      pypiOnset: "2024-11",
      npmOnset: "2025-08",
      reportOnset: "2025-03",
      jdOnset: "2025-09",
      paperToJdMonths: 81,
    },
    {
      capabilityId: "cap_06",
      name: "RAG/知识库",
      arxivOnset: "2019-05",
      pypiOnset: "2021-02",
      npmOnset: null,
      reportOnset: "2025-03",
      jdOnset: "2025-11",
      paperToJdMonths: 79,
    },
  ],
  note: "各层 onset = 首次达阈值月（论文 3 篇/包份额/日报 3 次/JD 2 次）",
};

const fmt = (v: string | null) => v ?? "—";

export default async function TimelinePage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  if (state === "error") {
    return (
      <AppShell>
        <FixtureState
          errorText="时间轴数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  }
  const data = isMockMode()
    ? MOCK
    : await apiFetch<Timeline>("/temporal/timeline");

  return (
    <AppShell>
      <section className="workflow-page" aria-labelledby="timeline-title">
        <header className="page-heading">
          <div className="title-with-meta">
            <h1 id="timeline-title">四层时间轴</h1>
            <span className="page-meta">
              论文 arXiv → 生态包 → 媒体传播 → 岗位需求 的技术传导
            </span>
          </div>
        </header>
        <p className="publish-hint">{data.note}</p>
        <div className="training-block">
          <table className="timeline-table">
            <thead>
              <tr>
                <th>能力域</th>
                <th>论文 arXiv</th>
                <th>PyPI 包</th>
                <th>npm 包</th>
                <th>日报传播</th>
                <th>JD 需求</th>
                <th>论文→JD</th>
              </tr>
            </thead>
            <tbody>
              {data.rows.map((r) => (
                <tr key={r.capabilityId}>
                  <td>{r.name}</td>
                  <td>{fmt(r.arxivOnset)}</td>
                  <td>{fmt(r.pypiOnset)}</td>
                  <td>{fmt(r.npmOnset)}</td>
                  <td>{fmt(r.reportOnset)}</td>
                  <td>{fmt(r.jdOnset)}</td>
                  <td>
                    {r.paperToJdMonths !== null
                      ? `${r.paperToJdMonths} 个月`
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
