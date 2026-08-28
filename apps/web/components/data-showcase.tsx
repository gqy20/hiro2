import Link from "next/link";
import type { DatasetOverview } from "@/lib/datasets";
import type { PipelineRunList } from "@/lib/pipeline-runs";
import { DataNav } from "@/components/data-nav";
import { DataKpiCard } from "@/components/data-kpi-card";

type Props = Readonly<{
  overview: DatasetOverview;
  pipeline: PipelineRunList;
}>;

const SOURCE_ORDER = ["jd", "temporal", "capability", "evidence", "resumes"] as const;
const PIPELINE_STAGES = ["ingest", "extract", "evidence", "signal"] as const;

const STAGE_LABEL: Record<string, string> = {
  ingest: "清洗",
  extract: "标准化",
  evidence: "证据化",
  signal: "信号化",
};

function todayRuns(runs: PipelineRunList["runs"]) {
  const today = new Date().toISOString().slice(0, 10);
  return runs.filter((r) => r.started_at.slice(0, 10) === today);
}

function latestByStage(runs: PipelineRunList["runs"]): Record<string, string> {
  const map: Record<string, string> = {};
  for (const stage of PIPELINE_STAGES) {
    const latest = runs.find((r) => r.component === stage);
    if (latest) map[stage] = latest.status.toUpperCase();
  }
  return map;
}

function formatNumber(n: number): string {
  return n.toLocaleString("zh-CN");
}

function statusClass(status: string | undefined): string {
  if (!status) return "is-idle";
  if (status === "SUCCEEDED") return "is-ok";
  if (status === "FAILED") return "is-fail";
  if (status === "RUNNING") return "is-running";
  return "is-idle";
}

export function DataShowcase({ overview, pipeline }: Props) {
  const sources = overview.datasets
    .filter((d) => (SOURCE_ORDER as readonly string[]).includes(d.id))
    .sort(
      (a, b) =>
        SOURCE_ORDER.indexOf(a.id as (typeof SOURCE_ORDER)[number]) -
        SOURCE_ORDER.indexOf(b.id as (typeof SOURCE_ORDER)[number]),
    );
  const stageStatuses = latestByStage(pipeline.runs);
  const today = todayRuns(pipeline.runs);
  const updatedAt = sources
    .map((s) => s.updated_at)
    .filter(Boolean)
    .sort()
    .at(-1);

  return (
    <section className="data-showcase" aria-labelledby="data-showcase-title">
      <h1 id="data-showcase-title" className="data-showcase-title">
        从原始素材到两个用户界面
      </h1>
      <DataNav />

      <div className="data-kpis" role="group" aria-label="数据规模">
        <DataKpiCard
          label="总记录数"
          value={formatNumber(overview.total_records)}
          meta={`${overview.total_datasets} 个数据集${updatedAt ? ` · ${updatedAt.slice(0, 10)} 更新` : ""}`}
          variant="primary"
          sparkline={[]}
        />
        <DataKpiCard
          label="今日处理"
          value={formatNumber(today.length)}
          meta="今日 pipeline run 次数"
          variant="secondary"
        />
      </div>

      <section className="data-panel" aria-labelledby="data-sources-title">
        <header className="data-panel-head">
          <h2 id="data-sources-title" className="data-panel-title">
            数据来源
          </h2>
          <Link className="data-panel-more" href="/data/sources">
            全部来源 →
          </Link>
        </header>
        <div className="data-source-grid">
          {sources.length === 0 ? (
            <p className="data-source-empty">暂无数据集</p>
          ) : (
            sources.map((s) => (
              <Link key={s.id} className="data-source-card" href="/data/sources">
                <span className="data-source-name">{s.name}</span>
                <strong className="data-source-value">{formatNumber(s.records)}</strong>
                <span className="data-source-meta">
                  {s.version} · {s.status}
                </span>
              </Link>
            ))
          )}
        </div>
      </section>

      <section className="data-panel" aria-labelledby="data-pipeline-title">
        <header className="data-panel-head">
          <h2 id="data-pipeline-title" className="data-panel-title">
            处理流水线
          </h2>
          <Link className="data-panel-more" href="/data/pipeline">
            近期运行 →
          </Link>
        </header>
        <ol className="data-pipeline-strip" aria-label="流水线四步">
          {PIPELINE_STAGES.map((stage) => {
            const status = stageStatuses[stage];
            return (
              <li className="data-pipeline-node" key={stage}>
                <span className="data-pipeline-label">{STAGE_LABEL[stage] ?? stage}</span>
                <span className={`data-pipeline-status ${statusClass(status)}`}>
                  {status ?? "暂无运行"}
                </span>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="data-panel" aria-labelledby="data-temporal-title">
        <header className="data-panel-head">
          <h2 id="data-temporal-title" className="data-panel-title">
            时间情报
          </h2>
        </header>
        <div className="data-temporal-row">
          <p className="data-temporal-text">
            论文 → 包 → 日报 → JD 四层信号传导时间轴
          </p>
          <Link className="data-panel-more" href="/temporal/timeline">
            查看完整时间轴 →
          </Link>
        </div>
      </section>

      <section className="data-panel" aria-labelledby="data-consumers-title">
        <header className="data-panel-head">
          <h2 id="data-consumers-title" className="data-panel-title">
            服务对象
          </h2>
        </header>
        <div className="data-consumer-grid">
          <Link className="data-consumer-card" href="/">
            <div className="data-consumer-info">
              <span className="data-consumer-label">招聘工作台</span>
              <span className="data-consumer-text">岗位决策与审核</span>
            </div>
            <span className="data-consumer-cta">进入 →</span>
          </Link>
          <Link className="data-consumer-card" href="/career">
            <div className="data-consumer-info">
              <span className="data-consumer-label">求职成长</span>
              <span className="data-consumer-text">能力诊断与学习路径</span>
            </div>
            <span className="data-consumer-cta">进入 →</span>
          </Link>
        </div>
      </section>
    </section>
  );
}
