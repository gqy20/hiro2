"use client";

import { useMemo, useState } from "react";
import { Segmented, Tag } from "antd";

import type { BacktestRun } from "@/lib/temporal";

type RulePair = {
  horizon: number;
  oldRun: BacktestRun;
  improvedRun: BacktestRun;
};

const errorLabels: Record<string, string> = {
  "up->down": "上升 → 下降",
  "down->up": "下降 → 上升",
  "up->flat": "上升 → 平稳",
  "down->flat": "下降 → 平稳",
  "flat->up": "平稳 → 上升",
  "flat->down": "平稳 → 下降",
};

function errorTone(transition: string): string {
  if (transition === "up->down" || transition === "down->up") return "severe";
  if (transition.startsWith("flat->")) return "missed";
  return "soft";
}

function percentage(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function points(value: number): string {
  const amount = value * 100;
  return `${amount > 0 ? "+" : ""}${amount.toFixed(1)}`;
}

export function TemporalRetrospectWorkbench({
  backtests,
}: {
  backtests: BacktestRun[];
}) {
  const rulePairs = useMemo(() => {
    const byHorizon = new Map<
      number,
      { oldRun?: BacktestRun; improvedRun?: BacktestRun }
    >();
    for (const run of backtests) {
      const pair = byHorizon.get(run.horizon_days) ?? {};
      if ((run.metrics.rule_version ?? 1) >= 2) pair.improvedRun = run;
      else pair.oldRun = run;
      byHorizon.set(run.horizon_days, pair);
    }

    return [...byHorizon.entries()]
      .sort(([a], [b]) => a - b)
      .flatMap(([horizon, pair]) =>
        pair.oldRun && pair.improvedRun
          ? [{ horizon, oldRun: pair.oldRun, improvedRun: pair.improvedRun }]
          : [],
      ) satisfies RulePair[];
  }, [backtests]);

  const initialHorizon =
    rulePairs[0]?.horizon ?? backtests[0]?.horizon_days ?? 30;
  const [horizon, setHorizon] = useState(initialHorizon);
  const selectedPair = rulePairs.find((pair) => pair.horizon === horizon);
  const run =
    selectedPair?.improvedRun ??
    backtests.find((item) => item.horizon_days === horizon) ??
    backtests[0];

  const errorList = useMemo(() => {
    if (!run) return [];
    return Object.entries(run.metrics.error_types)
      .map(([transition, count]) => ({ transition, count }))
      .sort((a, b) => b.count - a.count);
  }, [run]);

  if (!run) return null;

  const totalErrors = errorList.reduce((sum, error) => sum + error.count, 0);
  const maxErrors = Math.max(...errorList.map((error) => error.count), 1);
  const uplifts = rulePairs.map(
    ({ oldRun, improvedRun }) =>
      improvedRun.metrics.accuracy - oldRun.metrics.accuracy,
  );
  const allBelowBaseline = rulePairs.every(
    ({ improvedRun }) =>
      improvedRun.metrics.accuracy < improvedRun.metrics.flat_baseline_accuracy,
  );
  const minUplift = uplifts.length ? Math.min(...uplifts) : 0;
  const maxUplift = uplifts.length ? Math.max(...uplifts) : 0;
  const topError = errorList[0];
  const horizonOptions = rulePairs.length
    ? rulePairs.map((pair) => ({
        label: `${pair.horizon} 天`,
        value: pair.horizon,
      }))
    : [{ label: `${run.horizon_days} 天`, value: run.horizon_days }];

  return (
    <section className="temporal-workbench" aria-label="预测复盘">
      <section
        aria-label="规则评估结论"
        className={`temporal-verdict ${allBelowBaseline ? "is-warning" : "is-positive"}`}
      >
        <div>
          <Tag color={allBelowBaseline ? "orange" : "green"}>
            {allBelowBaseline ? "暂不采用" : "达到基线"}
          </Tag>
          <strong>
            {allBelowBaseline
              ? "改进有效，但仍未超过简单基线"
              : "改进规则已经达到简单基线"}
          </strong>
        </div>
        <p>
          {rulePairs.length > 0
            ? `三个预测周期提升 ${(minUplift * 100).toFixed(1)} 至 ${(maxUplift * 100).toFixed(1)} 个百分点${allBelowBaseline ? "，当前结果只用于继续调优。" : "。"}`
            : "当前缺少可配对的规则版本，暂时无法判断改进效果。"}
        </p>
      </section>

      {rulePairs.length > 0 ? (
        <section
          aria-labelledby="accuracy-compare-title"
          className="temporal-accuracy-compare"
        >
          <div className="temporal-section-title">
            <div>
              <h2 id="accuracy-compare-title">三周期准确率</h2>
              <p>
                同一批历史事件下，比较旧规则、改进规则与全部判为平稳的简单基线。
              </p>
            </div>
            <div aria-label="图例" className="temporal-compare-legend">
              <span className="is-old">旧规则</span>
              <span className="is-improved">改进规则</span>
              <span className="is-baseline">简单基线</span>
            </div>
          </div>
          <ol className="temporal-accuracy-list">
            {rulePairs.map(({ horizon: itemHorizon, oldRun, improvedRun }) => {
              const oldAccuracy = oldRun.metrics.accuracy;
              const improvedAccuracy = improvedRun.metrics.accuracy;
              const baseline = improvedRun.metrics.flat_baseline_accuracy;
              return (
                <li key={itemHorizon}>
                  <strong>{itemHorizon} 天</strong>
                  <div className="temporal-accuracy-bars">
                    <div>
                      <span>旧规则</span>
                      <i>
                        <b style={{ width: percentage(oldAccuracy) }} />
                      </i>
                      <em>{percentage(oldAccuracy)}</em>
                    </div>
                    <div className="is-improved">
                      <span>改进规则</span>
                      <i>
                        <b style={{ width: percentage(improvedAccuracy) }} />
                      </i>
                      <em>{percentage(improvedAccuracy)}</em>
                    </div>
                    <div className="is-baseline">
                      <span>简单基线</span>
                      <i>
                        <b style={{ width: percentage(baseline) }} />
                      </i>
                      <em>{percentage(baseline)}</em>
                    </div>
                  </div>
                  <div className="temporal-accuracy-deltas">
                    <span className="is-uplift">
                      提升 {points(improvedAccuracy - oldAccuracy)}
                    </span>
                    <span
                      className={
                        improvedAccuracy >= baseline ? "is-uplift" : "is-gap"
                      }
                    >
                      距基线 {points(improvedAccuracy - baseline)}
                    </span>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}

      <section
        aria-labelledby="error-title"
        className="temporal-backtest-errors temporal-retrospect-errors"
      >
        <div className="temporal-section-title">
          <div className="temporal-error-heading-copy">
            <h2 id="error-title">错误分布</h2>
            <p>
              {topError
                ? `最常见：预测${errorLabels[topError.transition]?.replace(" → ", "，实际") ?? topError.transition}，${topError.count} 次。`
                : "当前周期没有错误记录。"}
            </p>
          </div>
          <Segmented
            aria-label="选择预测周期"
            onChange={(value) => setHorizon(Number(value))}
            options={horizonOptions}
            value={horizon}
          />
        </div>
        <div className="temporal-error-axis" aria-hidden="true">
          <span>预测 -&gt; 实际</span>
          <span>错误次数</span>
        </div>
        <ol className="temporal-error-list">
          {errorList.map((error) => (
            <li
              className={`is-${errorTone(error.transition)}`}
              key={error.transition}
            >
              <span>{errorLabels[error.transition] ?? error.transition}</span>
              <i>
                <b style={{ width: `${(error.count / maxErrors) * 100}%` }} />
              </i>
              <strong>{error.count}</strong>
              <small>
                {totalErrors > 0
                  ? `${((error.count / totalErrors) * 100).toFixed(1)}%`
                  : "0%"}
              </small>
            </li>
          ))}
        </ol>
      </section>

      <details className="temporal-run-details">
        <summary>查看运行信息</summary>
        <dl>
          <div>
            <dt>运行 ID</dt>
            <dd>{run.run_id}</dd>
          </div>
          <div>
            <dt>截止日期</dt>
            <dd>{run.as_of_date || "未记录"}</dd>
          </div>
          <div>
            <dt>数据集版本</dt>
            <dd>
              {run.dataset_version && run.dataset_version !== "0"
                ? run.dataset_version
                : "未记录"}
            </dd>
          </div>
          <div>
            <dt>规则版本</dt>
            <dd>{`v${run.metrics.rule_version ?? 1}`}</dd>
          </div>
        </dl>
      </details>
    </section>
  );
}
