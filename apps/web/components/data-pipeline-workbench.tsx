"use client";

import { useMemo, useState } from "react";
import { Descriptions, Drawer, Empty, Table } from "antd";
import { apiFetch } from "@/lib/api/client";
import type { PipelineRun, PipelineRunDetail } from "@/lib/pipeline-runs";
import { formatTime } from "@/lib/time";

// RUNNING 超过该时长没有任何事件，视为僵死（worker 未写终态）
const STALE_MS = 30 * 60 * 1000;

type Props = Readonly<{
  runs: PipelineRun[];
  total: number;
  initialDetail: PipelineRunDetail | null;
  mockMode: boolean;
}>;

type SortKey = "run_id" | "component" | "status" | "duration_ms" | "started_at";

const SORT_COLUMNS: {
  key: SortKey | "count";
  label: string;
  numeric?: boolean;
  sortable: boolean;
}[] = [
  { key: "run_id", label: "运行 ID", sortable: true },
  { key: "component", label: "组件", sortable: true },
  { key: "status", label: "状态", sortable: true },
  { key: "duration_ms", label: "用时", numeric: true, sortable: true },
  { key: "count", label: "计数", sortable: false },
  { key: "started_at", label: "开始", sortable: true },
];

function sortValue(run: PipelineRun, key: SortKey): string | number {
  if (key === "duration_ms") return run.duration_ms ?? -1;
  return run[key] ?? "";
}

function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function isStale(run: PipelineRun): boolean {
  if (run.status !== "RUNNING") return false;
  const started = new Date(run.started_at).getTime();
  return Number.isFinite(started) && Date.now() - started > STALE_MS;
}

function statusClass(run: PipelineRun): string {
  if (isStale(run)) return "data-pipeline-row-status is-idle";
  const upper = run.status;
  if (upper === "SUCCEEDED") return "data-pipeline-row-status is-ok";
  if (upper === "FAILED") return "data-pipeline-row-status is-fail";
  if (upper === "RUNNING") return "data-pipeline-row-status is-running";
  return "data-pipeline-row-status is-idle";
}

function statusText(run: PipelineRun): string {
  if (isStale(run)) return "疑似中断";
  const upper = run.status;
  if (upper === "SUCCEEDED") return "✓ 成功";
  if (upper === "FAILED") return "✕ 失败";
  if (upper === "RUNNING") return "进行中";
  return run.status;
}

export function DataPipelineWorkbench({
  runs,
  total,
  initialDetail,
  mockMode,
}: Props) {
  const [stage, setStage] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("started_at");
  const [sortDesc, setSortDesc] = useState(true);
  const [detail, setDetail] = useState<PipelineRunDetail | null>(initialDetail);
  const [detailLoading, setDetailLoading] = useState(false);

  async function openRun(run: PipelineRun) {
    if (mockMode) return;
    setDetailLoading(true);
    try {
      setDetail(
        await apiFetch<PipelineRunDetail>(
          `/pipeline-runs/${encodeURIComponent(run.run_id)}`,
        ),
      );
    } finally {
      setDetailLoading(false);
    }
  }

  const filtered = useMemo(() => {
    const rows = runs.filter((r) => {
      if (stage !== "all" && r.component !== stage) return false;
      if (status !== "all" && r.status !== status) return false;
      return true;
    });
    const dir = sortDesc ? -1 : 1;
    return rows.sort((a, b) => {
      const va = sortValue(a, sortKey);
      const vb = sortValue(b, sortKey);
      if (typeof va === "number" && typeof vb === "number")
        return (va - vb) * dir;
      return String(va).localeCompare(String(vb)) * dir;
    });
  }, [runs, stage, status, sortKey, sortDesc]);

  function toggleSort(key: SortKey | "count") {
    if (key === "count") return;
    if (key === sortKey) setSortDesc((d) => !d);
    else {
      setSortKey(key);
      setSortDesc(key === "started_at" || key === "duration_ms");
    }
  }

  const statusOptions = useMemo(() => {
    const set = new Set(runs.map((r) => r.status));
    return ["all", ...Array.from(set)];
  }, [runs]);

  // 阶段下拉直接用真实组件名，不再套抽象四步
  const stageOptions = useMemo(() => {
    const set = new Set(runs.map((r) => r.component));
    return ["all", ...Array.from(set).sort()];
  }, [runs]);

  return (
    <section className="data-pipeline" aria-labelledby="data-pipeline-title">
      <div className="data-pipeline-head">
        <h1 id="data-pipeline-title" className="sr-only">
          流水线
        </h1>
        <span className="data-pipeline-count">
          {runs.length < total
            ? `显示最近 ${filtered.length} / 共 ${total} 次运行`
            : `${filtered.length} 次运行`}
        </span>
      </div>

      <div className="data-pipeline-table-wrap">
        <table className="t-table data-pipeline-table">
          <colgroup>
            <col className="col-id" />
            <col className="col-component" />
            <col className="col-status" />
            <col className="col-duration" />
            <col className="col-count" />
            <col className="col-time" />
          </colgroup>
          <thead>
            <tr>
              {SORT_COLUMNS.map((col) => {
                const isFilter =
                  col.key === "component" || col.key === "status";
                const sorted = !isFilter && col.sortable && sortKey === col.key;
                return (
                  <th
                    aria-sort={
                      sorted
                        ? sortDesc
                          ? "descending"
                          : "ascending"
                        : undefined
                    }
                    className={col.numeric ? "num" : undefined}
                    key={col.key}
                    scope="col"
                  >
                    {isFilter ? (
                      <select
                        aria-label={`按${col.label}筛选`}
                        className="col-filter"
                        onChange={(e) =>
                          col.key === "component"
                            ? setStage(e.target.value)
                            : setStatus(e.target.value)
                        }
                        value={col.key === "component" ? stage : status}
                      >
                        {(col.key === "component"
                          ? stageOptions
                          : statusOptions
                        ).map((s) => (
                          <option key={s} value={s}>
                            {s === "all" ? `${col.label} · 全部` : s}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <button
                        className={
                          sorted ? "table-sort is-active" : "table-sort"
                        }
                        onClick={() => toggleSort(col.key)}
                        type="button"
                      >
                        {col.label}
                        <span aria-hidden className="table-sort-arrow">
                          {sorted ? (sortDesc ? "↓" : "↑") : ""}
                        </span>
                      </button>
                    )}
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {filtered.length === 0 ? (
              <tr>
                <td className="data-pipeline-empty" colSpan={6}>
                  没有匹配运行
                </td>
              </tr>
            ) : (
              filtered.map((r) => (
                <tr
                  key={r.run_id}
                  onClick={() => void openRun(r)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      void openRun(r);
                    }
                  }}
                  tabIndex={0}
                >
                  <td className="data-pipeline-runid">{r.run_id}</td>
                  <td>{r.component}</td>
                  <td>
                    <span className={statusClass(r)}>{statusText(r)}</span>
                  </td>
                  <td className="num">{formatDuration(r.duration_ms)}</td>
                  <td className="data-pipeline-count-cell">
                    {r.count_summary || "—"}
                  </td>
                  <td className="data-pipeline-time">
                    {formatTime(r.started_at)}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      <Drawer
        loading={detailLoading}
        onClose={() => setDetail(null)}
        open={detail !== null || detailLoading}
        size="large"
        title={detail?.run.run_id ?? "运行详情"}
      >
        {detail ? <RunDetail detail={detail} /> : null}
      </Drawer>
    </section>
  );
}

function RunDetail({ detail }: { detail: PipelineRunDetail }) {
  return (
    <div className="data-run-detail">
      <Descriptions bordered column={2} size="small">
        <Descriptions.Item label="组件">
          {detail.run.component}
        </Descriptions.Item>
        <Descriptions.Item label="阶段">{detail.run.stage}</Descriptions.Item>
        <Descriptions.Item label="状态">{detail.run.status}</Descriptions.Item>
        <Descriptions.Item label="耗时">
          {formatDuration(detail.run.duration_ms)}
        </Descriptions.Item>
        <Descriptions.Item label="开始">
          {formatTime(detail.run.started_at)}
        </Descriptions.Item>
        <Descriptions.Item label="结束">
          {detail.run.finished_at ? formatTime(detail.run.finished_at) : "—"}
        </Descriptions.Item>
      </Descriptions>
      <section>
        <h3>运行配置</h3>
        <KeyValueTable value={detail.config} />
      </section>
      <section>
        <h3>指标与计数</h3>
        <KeyValueTable value={detail.metrics} />
      </section>
      <section>
        <h3>{`事件时间线 · ${detail.event_count}`}</h3>
        <Table<Record<string, unknown>>
          columns={[
            { title: "时间", dataIndex: "ts", width: 180 },
            { title: "阶段", dataIndex: "stage", width: 120 },
            { title: "事件", dataIndex: "event", width: 120 },
            { title: "状态", dataIndex: "status", width: 120 },
            {
              title: "摘要",
              render: (_, item) =>
                String(item.error_message ?? item.component ?? "—"),
            },
          ]}
          dataSource={detail.events}
          pagination={false}
          rowKey={(_, index) => String(index)}
          scroll={{ x: 760 }}
          size="small"
        />
      </section>
      <section>
        <h3>产物清单</h3>
        <ul>
          {detail.artifacts.map((artifact) => (
            <li key={artifact.name}>
              <code>{artifact.name}</code>
              <span>{`${artifact.size.toLocaleString("zh-CN")} bytes`}</span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function KeyValueTable({ value }: { value: Record<string, unknown> }) {
  const entries = Object.entries(value);
  if (!entries.length) return <Empty description="未记录" />;
  return (
    <dl className="data-run-key-values">
      {entries.map(([key, item]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>
            {typeof item === "object" ? JSON.stringify(item) : String(item)}
          </dd>
        </div>
      ))}
    </dl>
  );
}
