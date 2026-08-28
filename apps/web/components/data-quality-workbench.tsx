"use client";

import { useMemo } from "react";
import type { QualityOverview } from "@/lib/quality";

type Props = Readonly<{ quality: QualityOverview }>;

function formatPercent(value: number | null): string {
  if (value == null) return "暂无数据";
  return `${Math.round(value * 1000) / 10}%`;
}

function formatDays(value: number | null): string {
  if (value == null) return "暂无数据";
  return `${value} 天`;
}

function statusSource(source: string): string {
  if (source === "postgres") return "PostgreSQL";
  return "离线评测产物";
}

const ERROR_NOTES: Record<string, string> = {
  skill_误判: "同义词未归一或归一错误",
  范围遗漏: "应识别但未抽出的能力",
  证据不足: "缺少支撑原文片段",
  标签冲突: "两条规则结论矛盾",
  规则过时: "标准文档更新未同步",
};

export function DataQualityWorkbench({ quality }: Props) {
  // data_quality 标记区分“数值为 0”与“该指标不可用”：unavailable 一律显示暂无数据
  const flags = quality.data_quality;
  const available = (key: string) => flags[key] === "available";
  const completionRate = available("completion")
    ? quality.completion_rate
    : null;
  const dualReviewRate = available("dual_review")
    ? quality.dual_review_rate
    : null;
  const avgResponseDays = available("response_time")
    ? quality.avg_response_days
    : null;

  const errorList = useMemo(
    () =>
      available("errors")
        ? Object.entries(quality.error_distribution)
            .map(([key, count]) => ({ key, count: Number(count) }))
            .sort((a, b) => b.count - a.count)
        : [],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [quality.error_distribution, flags],
  );
  const maxErrorCount = errorList[0]?.count ?? 1;

  return (
    <section className="data-quality" aria-labelledby="data-quality-title">
      <h1 id="data-quality-title" className="sr-only">
        标注质量
      </h1>

      <div className="data-quality-kpis" role="group" aria-label="质量指标">
        <div className="data-quality-kpi">
          <span className="data-quality-kpi-label">任务完成率</span>
          <strong
            className={
              completionRate == null
                ? "data-quality-kpi-value is-empty"
                : "data-quality-kpi-value"
            }
          >
            {formatPercent(completionRate)}
          </strong>
          <span className="data-quality-kpi-meta">
            {quality.task_resolved} / {quality.task_total}
          </span>
        </div>
        <div className="data-quality-kpi">
          <span className="data-quality-kpi-label">双重审核率</span>
          <strong
            className={
              dualReviewRate == null
                ? "data-quality-kpi-value is-empty"
                : "data-quality-kpi-value"
            }
          >
            {formatPercent(dualReviewRate)}
          </strong>
          <span className="data-quality-kpi-meta">同任务至少两人审核</span>
        </div>
        <div className="data-quality-kpi">
          <span className="data-quality-kpi-label">平均响应</span>
          <strong
            className={
              avgResponseDays == null
                ? "data-quality-kpi-value is-empty"
                : "data-quality-kpi-value"
            }
          >
            {formatDays(avgResponseDays)}
          </strong>
          <span className="data-quality-kpi-meta">任务分配到提交</span>
        </div>
      </div>

      <section
        className="data-quality-panel"
        aria-labelledby="data-quality-errors-title"
      >
        <header className="data-quality-panel-head">
          <h2
            id="data-quality-errors-title"
            className="data-quality-panel-title"
          >
            错误类型分布
          </h2>
        </header>
        {errorList.length === 0 ? (
          <p className="data-quality-empty">暂无错误样本记录</p>
        ) : (
          <ul className="data-quality-errors">
            {errorList.map(({ key, count }, idx) => (
              <li
                className={
                  idx === 0
                    ? "data-quality-error-row is-top"
                    : "data-quality-error-row"
                }
                key={key}
              >
                <div className="data-quality-error-info">
                  <span className="data-quality-error-key">{key}</span>
                  {ERROR_NOTES[key] ? (
                    <span className="data-quality-error-note">
                      {ERROR_NOTES[key]}
                    </span>
                  ) : null}
                </div>
                <span className="data-quality-error-bar">
                  <i
                    style={{
                      width: `${Math.max((count / maxErrorCount) * 100, 2)}%`,
                    }}
                  />
                </span>
                <span className="data-quality-error-count">{count}</span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="data-quality-footer">
        <span>评测集版本：{quality.dataset_version || "—"}</span>
        <span>数据源：{statusSource(quality.source)}</span>
      </footer>
    </section>
  );
}
