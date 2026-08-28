"use client";

import { useEffect, useState } from "react";
import type { DatasetItem } from "@/lib/datasets";
import type { PipelineRun } from "@/lib/pipeline-runs";
import { formatTime } from "@/lib/time";

type Props = Readonly<{
  sources: DatasetItem[];
  stageRuns: Record<string, PipelineRun | undefined>;
}>;

const STAGES = [
  { key: "ingest", label: "清洗" },
  { key: "extract", label: "标准化" },
  { key: "evidence", label: "证据化" },
  { key: "signal", label: "信号化" },
] as const;

// viewBox 几何：左列来源节点、中部四步圆环节点、右列两个消费端
const VB_W = 1200;
const VB_H = 340;
const SRC_X = 30;
const SRC_W = 200;
const SRC_Y0 = 18;
const SRC_GAP = 60;
const STAGE_Y = 162;
const STAGE_R = 26;
const STAGE_X = [400, 520, 640, 760];
const DST_X = 970;
const DST_W = 200;
const DST_Y = [82, 197]; // 消费端节点中心 y = +28

function formatNumber(n: number): string {
  return n.toLocaleString("zh-CN");
}

// 节点 meta：版本号只保留 vN 段（jd-v3 → v3，前缀与节点名重复）；
// 状态为“可用”时不占文字（全部可用是常态，非常态才值得显示）
function nodeMeta(s: DatasetItem): string {
  const v = s.version.split("-").find((p) => /^v\d+/.test(p)) ?? s.version;
  return s.status === "可用" ? v : `${v} · ${s.status}`;
}

function stageStatusText(status: string | undefined): string {
  if (!status) return "暂无运行";
  if (status === "SUCCEEDED") return "✓ 成功";
  if (status === "FAILED") return "✕ 失败";
  if (status === "RUNNING") return "进行中";
  return status;
}

function stageColorClass(status: string | undefined): string {
  if (status === "SUCCEEDED") return "is-ok";
  if (status === "FAILED") return "is-fail";
  if (status === "RUNNING") return "is-running";
  return "is-idle";
}

function Dot({
  d,
  duration,
  delay,
}: {
  d: string;
  duration: number;
  delay: number;
}) {
  return (
    <circle
      className="fm-dot"
      r="2.5"
      style={{
        offsetPath: `path("${d}")`,
        animationDuration: `${duration}s`,
        animationDelay: `${delay}s`,
      }}
    />
  );
}

export function DataFlowMap({ sources, stageRuns }: Props) {
  const sourceNodes = sources.slice(0, 5);
  const convergePaths = sourceNodes.map((_, i) => {
    const y = SRC_Y0 + 24 + SRC_GAP * i;
    return `M ${SRC_X + SRC_W} ${y} C 320 ${y} 320 ${STAGE_Y} ${STAGE_X[0] - STAGE_R} ${STAGE_Y}`;
  });
  const segmentPaths = STAGE_X.slice(0, -1).map(
    (x) => `M ${x + STAGE_R} ${STAGE_Y} L ${x + 120 - STAGE_R} ${STAGE_Y}`,
  );
  const branchPaths = DST_Y.map(
    (y) =>
      `M ${STAGE_X.at(-1)! + STAGE_R} ${STAGE_Y} C 880 ${STAGE_Y} 880 ${y + 28} ${DST_X} ${y + 28}`,
  );
  const [selected, setSelected] = useState<string | null>(null);

  return (
    <div className="data-flow-layout">
      <figure className="data-flow-wrap" aria-label="数据流转全景">
        <svg
          className="data-flow-map"
          role="img"
          aria-label="数据流转全景：数据源经清洗、标准化、证据化、信号化四步，汇入招聘工作台与求职成长两个界面"
          viewBox={`0 0 ${VB_W} ${VB_H}`}
        >
          {/* 连线：底线 + 流动虚线 */}
          {[...convergePaths, ...segmentPaths, ...branchPaths].map((d) => (
            <g key={d}>
              <path className="fm-line" d={d} />
              <path className="fm-flow" d={d} />
            </g>
          ))}
          {/* 流动光点 */}
          {convergePaths.map((d, i) => (
            <Dot d={d} delay={-i * 1.4} duration={7} key={d} />
          ))}
          {segmentPaths.map((d, i) => (
            <Dot d={d} delay={-i * 1.1} duration={3} key={d} />
          ))}
          {branchPaths.map((d, i) => (
            <Dot d={d} delay={-i * 2.3} duration={5} key={d} />
          ))}

          {/* 左：数据源 */}
          {sourceNodes.map((s, i) => {
            const y = SRC_Y0 + SRC_GAP * i;
            return (
              <a
                aria-expanded={selected === s.id}
                className={
                  selected === s.id
                    ? "fm-node data-flow-source is-active"
                    : "fm-node data-flow-source"
                }
                href="/data/sources"
                key={s.id}
                onClick={(e) => {
                  e.preventDefault();
                  // 再点同一节点收起
                  setSelected((prev) => (prev === s.id ? null : s.id));
                }}
              >
                <rect
                  className="fm-rect"
                  height={48}
                  rx={12}
                  width={SRC_W}
                  x={SRC_X}
                  y={y}
                />
                <text className="fm-name" x={SRC_X + 14} y={y + 19}>
                  {s.name}
                </text>
                <text className="fm-meta" x={SRC_X + 14} y={y + 37}>
                  {nodeMeta(s)}
                </text>
                <text
                  className="fm-value"
                  textAnchor="end"
                  x={SRC_X + SRC_W - 14}
                  y={y + 37}
                >
                  {formatNumber(s.records)}
                </text>
              </a>
            );
          })}

          {/* 中：四步流水线 */}
          {STAGES.map((stage, i) => {
            const run = stageRuns[stage.key];
            const cls = stageColorClass(run?.status.toUpperCase());
            return (
              <a
                className="fm-node data-flow-stage"
                href="/data/pipeline"
                key={stage.key}
              >
                <circle
                  className={`fm-ring ${cls}`}
                  cx={STAGE_X[i]}
                  cy={STAGE_Y}
                  r={STAGE_R}
                />
                <text
                  className="fm-stage-label"
                  textAnchor="middle"
                  x={STAGE_X[i]}
                  y={STAGE_Y + 4}
                >
                  {stage.label}
                </text>
                <text
                  className={`fm-stage-status ${cls}`}
                  textAnchor="middle"
                  x={STAGE_X[i]}
                  y={STAGE_Y + 44}
                >
                  {stageStatusText(run?.status.toUpperCase())}
                </text>
                {run?.started_at ? (
                  <text
                    className="fm-stage-time"
                    textAnchor="middle"
                    x={STAGE_X[i]}
                    y={STAGE_Y + 58}
                  >
                    {formatTime(run.started_at)}
                  </text>
                ) : null}
              </a>
            );
          })}

          {/* 右：消费端（SVG 内无法用 next/link，原生 <a> 为唯一选择） */}
          {/* eslint-disable-next-line @next/next/no-html-link-for-pages */}
          <a className="fm-node" href="/">
            <rect
              className="fm-rect fm-rect-end"
              height={56}
              rx={12}
              width={DST_W}
              x={DST_X}
              y={DST_Y[0]}
            />
            <text
              className="fm-name fm-name-strong"
              x={DST_X + 16}
              y={DST_Y[0] + 23}
            >
              招聘工作台
            </text>
            <text className="fm-meta" x={DST_X + 16} y={DST_Y[0] + 41}>
              岗位决策与审核
            </text>
          </a>
          <a className="fm-node" href="/career">
            <rect
              className="fm-rect fm-rect-end"
              height={56}
              rx={12}
              width={DST_W}
              x={DST_X}
              y={DST_Y[1]}
            />
            <text
              className="fm-name fm-name-strong"
              x={DST_X + 16}
              y={DST_Y[1] + 23}
            >
              求职成长
            </text>
            <text className="fm-meta" x={DST_X + 16} y={DST_Y[1] + 41}>
              能力诊断与学习路径
            </text>
          </a>
        </svg>
      </figure>

      {selected ? (
        <SourceDrawer
          dataset={sources.find((s) => s.id === selected)}
          onClose={() => setSelected(null)}
        />
      ) : null}
    </div>
  );
}

// 来源类型与采集模式的中文展示标签（SOURCES.yml 的英文枚举仅保留在代码层）
const TYPE_LABELS: Record<string, string> = {
  expert_matrix: "专家矩阵",
  government_policy: "政府政策",
  occupational_database: "职业数据库",
  academic_dataset: "学术数据集",
  academic_preprint: "预印本论文",
  job_board: "招聘平台",
  web_archive: "网页存档",
  employer_site: "企业官网",
  occupation_standard: "职业标准",
  industry_media: "产业媒体",
  rss_direct: "RSS 订阅",
  package_registry: "包仓库",
};

const MODE_LABELS: Record<string, string> = {
  backfill: "历史回填",
  live: "实时采集",
};

// 无外部来源登记的数据集（派生/受控）展示说明，不包含任何编造数字
const DERIVED_NOTES: Record<string, string> = {
  evidence: "由岗位、日报与标准数据派生的分析产物，无独立外部来源。",
  resumes: "候选人上传与受控导入，按隐私要求不登记外部来源。",
  evaluation: "冻结标注集，仅用于评测，不参与日常流转。",
};

function SourceDetail({
  dataset,
  onClose,
}: {
  dataset: DatasetItem | undefined;
  onClose: () => void;
}) {
  if (!dataset) return null;
  const sources = dataset.sources ?? [];
  return (
    <div className="data-flow-source-detail">
      <div className="data-flow-source-detail-head">
        <div>
          <strong className="data-flow-source-detail-title">
            {dataset.name}
          </strong>
          <span className="data-flow-source-detail-meta">
            {dataset.version} · {dataset.status}
          </span>
        </div>
        <button aria-label="关闭明细" autoFocus onClick={onClose} type="button">
          ✕
        </button>
      </div>
      <dl className="data-flow-source-detail-stats">
        <div>
          <dt>记录</dt>
          <dd>{dataset.records.toLocaleString("zh-CN")}</dd>
        </div>
        <div>
          <dt>有效</dt>
          <dd>{dataset.valid_records.toLocaleString("zh-CN")}</dd>
        </div>
        <div>
          <dt>质量</dt>
          <dd>{dataset.quality}%</dd>
        </div>
        <div>
          <dt>最近更新</dt>
          <dd>{dataset.updated_at ? dataset.updated_at.slice(0, 10) : "—"}</dd>
        </div>
      </dl>
      <section aria-label="来源通道" className="data-flow-source-channels">
        <h3 className="data-flow-source-channels-title">
          {sources.length ? `来源通道 · ${sources.length}` : "来源说明"}
        </h3>
        {sources.length ? (
          <ul className="data-flow-source-channels-list">
            {sources.map((s) => (
              <li key={s.id}>
                <div className="data-flow-source-channel-head">
                  <strong>{s.id}</strong>
                  <span className="data-flow-source-channel-type">
                    {TYPE_LABELS[s.type] ?? s.type}
                  </span>
                </div>
                <div className="data-flow-source-channel-meta">
                  {s.time_range.length === 2
                    ? `${s.time_range[0]} ~ ${s.time_range[1]}`
                    : ""}
                  {s.ingestion_mode
                    ? ` · ${MODE_LABELS[s.ingestion_mode] ?? s.ingestion_mode}`
                    : ""}
                </div>
                {s.notes ? (
                  <p className="data-flow-source-channel-notes">{s.notes}</p>
                ) : null}
              </li>
            ))}
          </ul>
        ) : (
          <p className="data-flow-source-derived">
            {DERIVED_NOTES[dataset.id] ?? dataset.source}
          </p>
        )}
      </section>
    </div>
  );
}

// 抽屉容器：与 /datasets 的 dataset-drawer 同一交互模式——右侧滑入、
// 点遮罩 / Esc / 再点同一来源关闭，不再挤占主内容宽度
export function SourceDrawer({
  dataset,
  onClose,
}: {
  dataset: DatasetItem | undefined;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  if (!dataset) return null;
  return (
    <div
      className="dataset-drawer-backdrop"
      role="presentation"
      onClick={onClose}
    >
      <aside
        aria-label={dataset.name}
        aria-modal="true"
        className="dataset-drawer"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
      >
        <SourceDetail dataset={dataset} onClose={onClose} />
      </aside>
    </div>
  );
}

export { SourceDetail };
