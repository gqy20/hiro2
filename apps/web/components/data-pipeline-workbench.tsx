"use client";

import { useMemo, useState } from "react";
import { DataNav } from "@/components/data-nav";
import type { PipelineRun } from "@/lib/pipeline-runs";

type Props = Readonly<{ runs: PipelineRun[] }>;

const STAGES = [
  { key: "ingest", label: "清洗" },
  { key: "extract", label: "标准化" },
  { key: "evidence", label: "证据化" },
  { key: "signal", label: "信号化" },
] as const;

function formatDuration(ms: number | null): string {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return `${date.toISOString().slice(5, 10)} ${date.toISOString().slice(11, 16)}`;
}

function statusClass(status: string): string {
  const upper = status.toUpperCase();
  if (upper === "SUCCEEDED") return "data-pipeline-row-status is-ok";
  if (upper === "FAILED") return "data-pipeline-row-status is-fail";
  if (upper === "RUNNING") return "data-pipeline-row-status is-running";
  return "data-pipeline-row-status is-idle";
}

function statusText(status: string): string {
  const upper = status.toUpperCase();
  if (upper === "SUCCEEDED") return "✓ 成功";
  if (upper === "FAILED") return "✕ 失败";
  if (upper === "RUNNING") return "进行中";
  return status;
}

export function DataPipelineWorkbench({ runs }: Props) {
  const [stage, setStage] = useState<string>("all");
  const [status, setStatus] = useState<string>("all");

  const stageStatuses = useMemo(() => {
    const map: Record<string, string> = {};
    for (const s of STAGES) {
      const latest = runs.find((r) => r.component === s.key);
      if (latest) map[s.key] = latest.status.toUpperCase();
    }
    return map;
  }, [runs]);

  const filtered = useMemo(() => {
    return runs.filter((r) => {
      if (stage !== "all" && r.component !== stage) return false;
      if (status !== "all" && r.status.toUpperCase() !== status) return false;
      return true;
    });
  }, [runs, stage, status]);

  const statusOptions = useMemo(() => {
    const set = new Set(runs.map((r) => r.status.toUpperCase()));
    return ["all", ...Array.from(set)];
  }, [runs]);

  return (
    <section className="data-pipeline" aria-labelledby="data-pipeline-title">
      <h1 id="data-pipeline-title" className="data-pipeline-title">
        处理流水线
      </h1>
      <DataNav />

      <ol className="data-pipeline-strip" aria-label="流水线四步">
        {STAGES.map((s) => {
          const st = stageStatuses[s.key];
          const cls = !st
            ? "is-idle"
            : st === "SUCCEEDED"
              ? "is-ok"
              : st === "FAILED"
                ? "is-fail"
                : "is-running";
          return (
            <li className="data-pipeline-node" key={s.key}>
              <span className="data-pipeline-label">{s.label}</span>
              <span className={`data-pipeline-status ${cls}`}>
                {st ?? "暂无运行"}
              </span>
            </li>
          );
        })}
      </ol>

      <div className="data-pipeline-toolbar" role="group" aria-label="筛选">
        <label className="data-pipeline-field">
          <span>阶段</span>
          <select onChange={(e) => setStage(e.target.value)} value={stage}>
            <option value="all">全部</option>
            {STAGES.map((s) => (
              <option key={s.key} value={s.key}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label className="data-pipeline-field">
          <span>状态</span>
          <select onChange={(e) => setStatus(e.target.value)} value={status}>
            {statusOptions.map((s) => (
              <option key={s} value={s}>
                {s === "all" ? "全部" : s}
              </option>
            ))}
          </select>
        </label>
        <span className="data-pipeline-count">
          {filtered.length} / {runs.length} 次运行
        </span>
      </div>

      <div className="data-pipeline-table-wrap">
        <table className="data-pipeline-table">
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
              <th scope="col">运行 ID</th>
              <th scope="col">组件</th>
              <th scope="col">状态</th>
              <th scope="col" className="num">用时</th>
              <th scope="col">计数</th>
              <th scope="col">开始</th>
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
                    <span className={statusClass(r.status)}>
                      {statusText(r.status)}
                    </span>
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
