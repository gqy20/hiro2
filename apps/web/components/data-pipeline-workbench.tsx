"use client";

import { useMemo, useState } from "react";
import type { PipelineRun } from "@/lib/pipeline-runs";
import { formatTime } from "@/lib/time";

// RUNNING 超过该时长没有任何事件，视为僵死（worker 未写终态）
const STALE_MS = 30 * 60 * 1000;

type Props = Readonly<{ runs: PipelineRun[]; total: number }>;

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

export function DataPipelineWorkbench({ runs, total }: Props) {
  const [stage, setStage] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");
  const [sortKey, setSortKey] = useState<SortKey>("started_at");
  const [sortDesc, setSortDesc] = useState(true);

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
          处理流水线
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
                <tr key={r.run_id}>
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
    </section>
  );
}
