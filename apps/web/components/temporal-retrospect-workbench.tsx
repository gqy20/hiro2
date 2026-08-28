"use client";

import { useMemo, useState } from "react";
import { Progress, Statistic, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/workflow-ui";
import { TemporalNav } from "@/components/temporal-nav";
import type { BacktestRun } from "@/lib/temporal";

function accuracyTone(
  acc: number,
  baseline: number,
): "success" | "exception" | "normal" {
  if (acc >= baseline) return "success";
  if (acc < baseline * 0.85) return "exception";
  return "normal";
}

export function TemporalRetrospectWorkbench({
  backtests,
}: {
  backtests: BacktestRun[];
}) {
  const [runId, setRunId] = useState(backtests[0]?.run_id ?? "");
  const run = backtests.find((b) => b.run_id === runId) ?? backtests[0];

  // 规则版本对比：按 horizon 配对 v1/v2（评测驱动迭代的证据）
  const ruleCompare = useMemo(() => {
    const byHorizon = new Map<number, { v1?: BacktestRun; v2?: BacktestRun }>();
    for (const b of backtests) {
      const rule = b.metrics.rule_version ?? 1;
      const entry = byHorizon.get(b.horizon_days) ?? {};
      if (rule >= 2) entry.v2 = b;
      else entry.v1 = b;
      byHorizon.set(b.horizon_days, entry);
    }
    return [...byHorizon.entries()]
      .sort((a, b) => a[0] - b[0])
      .filter(([, v]) => v.v1 && v.v2);
  }, [backtests]);

  const errorList = useMemo(() => {
    if (!run) return [];
    return Object.entries(run.metrics.error_types)
      .map(([transition, count]) => ({ transition, count }))
      .sort((a, b) => b.count - a.count);
  }, [run]);

  if (!run) {
    return null;
  }

  return (
    <AppShell>
      <section
        className="temporal-workbench"
        aria-labelledby="retrospect-title"
      >
        <header className="page-heading">
          <h1 id="retrospect-title">预测复盘</h1>
          <p>{`3 个 horizon 回测结果，命中率对比`}</p>
        </header>
        <TemporalNav />

        {ruleCompare.length > 0 ? (
          <section aria-label="规则版本对比" className="temporal-rule-compare">
            <SectionHeader
              meta="回测驱动"
              title="规则迭代对比（同一批历史事件）"
            />
            <ul>
              {ruleCompare.map(([horizon, v]) => {
                const v1 = v.v1!.metrics.accuracy;
                const v2 = v.v2!.metrics.accuracy;
                const delta = v2 - v1;
                return (
                  <li key={horizon}>
                    <span className="temporal-rule-horizon">h{horizon}</span>
                    <span>v1 {(v1 * 100).toFixed(1)}%</span>
                    <b>→</b>
                    <span className="temporal-rule-v2">
                      v2 {(v2 * 100).toFixed(1)}%
                    </span>
                    <Tag color={delta > 0 ? "green" : "red"}>
                      {delta > 0 ? "+" : ""}
                      {(delta * 100).toFixed(1)}
                    </Tag>
                    <small>
                      平基线 {`${(v.v2!.metrics.flat_baseline_accuracy * 100).toFixed(1)}%`}
                    </small>
                  </li>
                );
              })}
            </ul>
            <p className="temporal-rule-note">
              v2 由 v1 回测错误分析推导（过热抑制 + down 保守化）；仍逊平基线如实呈现。
            </p>
          </section>
        ) : null}

        <div className="temporal-filters">
          {backtests.map((b) => (
            <button
              aria-pressed={b.run_id === runId}
              className={`temporal-filter-tab ${
                b.run_id === runId ? "is-active" : ""
              }`}
              key={b.run_id}
              onClick={() => setRunId(b.run_id)}
              type="button"
            >
              {`h${b.horizon_days} · v${b.metrics.rule_version ?? 1} · 命中率 ${(b.metrics.accuracy * 100).toFixed(0)}%`}
            </button>
          ))}
        </div>

        <section aria-label="指标" className="temporal-backtest-metrics">
          <div className="temporal-stat-card">
            <Statistic
              title="回测命中率"
              value={run.metrics.accuracy}
              valueStyle={{
                color:
                  accuracyTone(
                    run.metrics.accuracy,
                    run.metrics.flat_baseline_accuracy,
                  ) === "success"
                    ? "var(--green)"
                    : "var(--red)",
              }}
              precision={3}
            />
            <Progress
              percent={Math.round(run.metrics.accuracy * 100)}
              showInfo={false}
              size="small"
              status={accuracyTone(
                run.metrics.accuracy,
                run.metrics.flat_baseline_accuracy,
              )}
            />
          </div>
          <div className="temporal-stat-card">
            <Statistic
              title="全平基线"
              value={run.metrics.flat_baseline_accuracy}
              precision={3}
            />
            <small>{"as_of 基准：所有预测都判为 flat"}</small>
          </div>
          <div className="temporal-stat-card">
            <Statistic title="horizon 天数" value={run.horizon_days} />
          </div>
          <div className="temporal-stat-card">
            <Statistic
              title="数据集版本"
              value={run.dataset_version}
              valueStyle={{ fontSize: 14 }}
            />
          </div>
        </section>

        <section aria-label="误差分布" className="temporal-backtest-errors">
          <SectionHeader meta={`${errorList.length} 类`} title="误差类型分布" />
          <ul>
            {errorList.map((e) => (
              <li className="temporal-backtest-error-row" key={e.transition}>
                <Tag
                  color={
                    e.transition.startsWith("up->")
                      ? "green"
                      : e.transition.startsWith("down->")
                        ? "red"
                        : "blue"
                  }
                >
                  {e.transition}
                </Tag>
                <span>{e.count} 次</span>
                <Progress
                  percent={Math.round(
                    (e.count / Math.max(...errorList.map((x) => x.count))) *
                      100,
                  )}
                  showInfo={false}
                  size="small"
                />
              </li>
            ))}
          </ul>
        </section>
      </section>
    </AppShell>
  );
}
