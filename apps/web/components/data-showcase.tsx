import type { DatasetOverview } from "@/lib/datasets";
import type { PipelineRun, PipelineRunList } from "@/lib/pipeline-runs";
import { formatDate, todayStr } from "@/lib/time";
import { DataFlowMap } from "@/components/data-flow-map";
import { DataKpiCard } from "@/components/data-kpi-card";

type Props = Readonly<{
  overview: DatasetOverview;
  pipeline: PipelineRunList;
}>;

const SOURCE_ORDER = [
  "jd",
  "temporal",
  "capability",
  "evidence",
  "resumes",
] as const;
const PIPELINE_STAGES = ["ingest", "extract", "evidence", "signal"] as const;

function todayRuns(runs: PipelineRunList["runs"]) {
  const today = todayStr();
  return runs.filter((r) => formatDate(r.started_at) === today);
}

// 后端在 View Model 层输出规范化 stage（ingest/extract/evidence/signal/other），
// 前端不再按 component 猜测阶段
function latestByStage(runs: PipelineRunList["runs"]) {
  const map: Record<string, PipelineRun | undefined> = {};
  for (const stage of PIPELINE_STAGES) {
    if (!map[stage]) map[stage] = runs.find((r) => r.stage === stage);
  }
  return map;
}

function formatNumber(n: number): string {
  return n.toLocaleString("zh-CN");
}

// 占比展示：0 与非 0 要有区分，非 0 不足 0.1% 时不能四舍五入成 0%
function formatPct(part: number, total: number): string {
  if (part <= 0 || total <= 0) return "0%";
  const pct = (part / total) * 100;
  if (pct < 0.1) return "<0.1%";
  if (pct < 1) return `${pct.toFixed(1)}%`;
  return `${Math.round(pct)}%`;
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
  const todayOk = today.filter((r) => r.status === "SUCCEEDED").length;
  const todayFail = today.filter((r) => r.status === "FAILED").length;
  const todayRunning = today.filter(
    (r) =>
      r.status === "RUNNING" ||
      r.status === "PENDING" ||
      r.status === "RETRYING",
  ).length;
  const todaySuffixParts = [
    todayOk ? `成功 ${todayOk}` : "",
    todayRunning ? `进行中 ${todayRunning}` : "",
    todayFail ? `失败 ${todayFail}` : "",
  ].filter(Boolean);
  const pendingPct = formatPct(
    overview.pending_records,
    overview.total_records,
  );
  const updatedAt = sources
    .map((s) => s.updated_at)
    .filter(Boolean)
    .sort()
    .at(-1);

  return (
    <section className="data-showcase" aria-labelledby="data-showcase-title">
      {/* 视觉标题由顶部导航承担，此处仅保留无障碍大纲 */}
      <h1 id="data-showcase-title" className="sr-only">
        数据总览
      </h1>

      <div className="data-kpis" role="group" aria-label="数据规模">
        <DataKpiCard
          label="总记录数"
          value={formatNumber(overview.total_records)}
          suffix={`${overview.total_datasets} 个数据集${updatedAt ? ` · ${updatedAt.slice(5, 10)} 更新` : ""}`}
        />
        <DataKpiCard
          label="今日处理"
          value={formatNumber(today.length)}
          suffix={today.length ? todaySuffixParts.join(" · ") : "今日暂无运行"}
        />
        <DataKpiCard
          label="就绪数据集"
          value={formatNumber(overview.ready_datasets)}
          suffix={`/ ${overview.total_datasets} 个数据集`}
        />
        <DataKpiCard
          label="待处理记录"
          value={formatNumber(overview.pending_records)}
          suffix={`条 · 占总量 ${pendingPct}`}
        />
      </div>

      <DataFlowMap sources={sources} stageRuns={stageStatuses} />
    </section>
  );
}
