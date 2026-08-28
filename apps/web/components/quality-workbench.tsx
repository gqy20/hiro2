"use client";

import { useMemo, useState } from "react";
import { Progress, Statistic, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/workflow-ui";
import type { TemporalDataset } from "@/lib/temporal";
import type { QualityOverview } from "@/lib/quality";

const ERROR_LABELS: Record<string, string> = {
  skill_误判: "技能误判",
  范围遗漏: "范围遗漏",
  证据不足: "证据不足",
  标签冲突: "标签冲突",
  规则过时: "规则过时",
  其他: "其他",
};

export function QualityWorkbench({
  temporal,
  quality,
  embedded = false,
}: {
  temporal: TemporalDataset;
  quality: QualityOverview;
  embedded?: boolean;
}) {
  const [compareIds, setCompareIds] = useState<[string, string]>(() => [
    temporal.backtests[0].run_id,
    temporal.backtests[1].run_id,
  ]);

  const backtestOptions = useMemo(
    () => temporal.backtests.map((b) => ({ label: b.run_id, value: b.run_id })),
    [temporal],
  );

  const a = temporal.backtests.find((b) => b.run_id === compareIds[0]);
  const b = temporal.backtests.find((bb) => bb.run_id === compareIds[1]);

  const errorList = useMemo(
    () =>
      Object.entries(quality.error_distribution)
        .map(([key, count]) => ({
          key,
          label: ERROR_LABELS[key] ?? key,
          count,
        }))
        .sort((x, y) => y.count - x.count),
    [quality.error_distribution],
  );
  const maxErrorCount = errorList[0]?.count ?? 1;

  return (
    <AppShell>
      <section
        className="quality-workbench"
        {...(embedded
          ? { "aria-label": "运行对比与错误分布" }
          : { "aria-labelledby": "quality-title" })}
      >
        {embedded ? null : (
          <header className="page-heading">
            <h1 id="quality-title">质量看板</h1>
            <p>
              评测任务、审核动作与回测运行的质量汇总 · 数据源：
              {quality.source === "postgres" ? "PostgreSQL" : "离线评测产物"}
            </p>
          </header>
        )}

        <section aria-label="核心指标" className="temporal-backtest-metrics">
          <div className="temporal-stat-card">
            <Statistic
              title="任务完成率"
              value={quality.completion_rate}
              styles={{ content: { color: "var(--green)" } }}
              precision={2}
            />
            <Progress
              percent={Math.round(quality.completion_rate * 100)}
              showInfo={false}
              size="small"
              status="success"
            />
          </div>
          <div className="temporal-stat-card">
            <Statistic
              title="双人复核率"
              value={quality.dual_review_rate ?? 0}
              precision={2}
            />
            <Progress
              percent={Math.round((quality.dual_review_rate ?? 0) * 100)}
              showInfo={false}
              size="small"
            />
          </div>
          <div className="temporal-stat-card">
            <Statistic
              title="平均响应时长（天）"
              value={quality.avg_response_days ?? "暂无"}
              precision={1}
            />
          </div>
          <div className="temporal-stat-card">
            <Statistic title="已解决任务" value={quality.task_resolved} />
          </div>
        </section>

        <section aria-label="错误分布" className="temporal-backtest-errors">
          <SectionHeader meta={`${errorList.length} 类`} title="错误类型分布" />
          <ul>
            {errorList.map((e) => (
              <li className="temporal-backtest-error-row" key={e.key}>
                <Tag>{e.label}</Tag>
                <span>{e.count} 次</span>
                <Progress
                  percent={Math.round((e.count / maxErrorCount) * 100)}
                  showInfo={false}
                  size="small"
                />
              </li>
            ))}
          </ul>
        </section>

        <section aria-label="Run 对比" className="temporal-backtest-errors">
          <SectionHeader title="Run 对比" />
          <div className="temporal-filters">
            <span>A</span>
            <select
              aria-label="Run A"
              onChange={(e) => {
                const next: [string, string] = [e.target.value, compareIds[1]];
                setCompareIds(next);
              }}
              value={compareIds[0]}
            >
              {backtestOptions.map((o: { label: string; value: string }) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <span>vs</span>
            <select
              aria-label="Run B"
              onChange={(e) => {
                const next: [string, string] = [compareIds[0], e.target.value];
                setCompareIds(next);
              }}
              value={compareIds[1]}
            >
              {backtestOptions.map((o: { label: string; value: string }) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </div>
          <div className="temporal-backtest-metrics">
            {a ? (
              <div className="temporal-stat-card">
                <Statistic
                  title={`Run A · ${a.run_id}`}
                  value={a.metrics.accuracy}
                  precision={3}
                />
                <small>{`horizon ${a.horizon_days} 天`}</small>
              </div>
            ) : null}
            {b ? (
              <div className="temporal-stat-card">
                <Statistic
                  title={`Run B · ${b.run_id}`}
                  value={b.metrics.accuracy}
                  precision={3}
                />
                <small>{`horizon ${b.horizon_days} 天`}</small>
              </div>
            ) : null}
            {a && b ? (
              <div className="temporal-stat-card">
                <Statistic
                  title="差异"
                  value={a.metrics.accuracy - b.metrics.accuracy}
                  precision={3}
                  styles={{
                    content: {
                      color:
                        a.metrics.accuracy >= b.metrics.accuracy
                          ? "var(--green)"
                          : "var(--red)",
                    },
                  }}
                />
                <small>{"A 减 B，正数 = A 优"}</small>
              </div>
            ) : null}
          </div>
        </section>
      </section>
    </AppShell>
  );
}
