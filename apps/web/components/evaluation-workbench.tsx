"use client";

import { useState, type ReactNode } from "react";
import { ArrowRight, Database } from "@phosphor-icons/react";
import { Drawer, Progress, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/workflow-ui";
import type { EvaluationOverview } from "@/lib/evaluation";

// ponytail: 后端 B-T4 未开始；契约里也没有 EvaluationMetrics；
// 数据全部 inline 在组件内，不抽 lib/evaluation.ts。

function metricTone(value: number): "success" | "normal" {
  return value >= 0.7 ? "success" : "normal";
}

type EvaluationError = EvaluationOverview["errors"][number];
type EvaluationCase = EvaluationOverview["cases"][number];

const DIRECTIONS = ["up", "flat", "down"] as const;
const DIRECTION_LABELS = { up: "上升", flat: "平稳", down: "下降" };
const SEVERITY_META = {
  critical: { color: "red", label: "严重偏差" },
  high: { color: "orange", label: "趋势漏判" },
  medium: { color: "blue", label: "趋势误报" },
} as const;

export function EvaluationWorkbench({
  overview,
  extra,
}: {
  overview: EvaluationOverview;
  extra?: ReactNode;
}) {
  const [selectedError, setSelectedError] = useState<EvaluationError | null>(
    null,
  );
  const currentRun = {
    ...overview.run,
    dataset: overview.datasets[0]?.id ?? "",
    metrics: overview.metrics,
    errors: overview.errors,
  };
  const datasets = overview.datasets;
  const cases = overview.cases ?? [];
  const summary = overview.summary ?? {
    total: cases.length,
    hits: cases.filter((item) => item.hit).length,
    errors: cases.filter((item) => !item.hit).length,
    accuracy: 0,
    baselineAccuracy: 0,
  };
  const selectedCases = selectedError
    ? cases.filter(
        (item) =>
          !item.hit &&
          item.predicted === selectedError.predicted &&
          item.actual === selectedError.actual,
      )
    : [];

  function matrixCount(
    predicted: EvaluationCase["predicted"],
    actual: EvaluationCase["actual"],
  ): number {
    return cases.filter(
      (item) => item.predicted === predicted && item.actual === actual,
    ).length;
  }

  function matrixError(
    predicted: EvaluationCase["predicted"],
    actual: EvaluationCase["actual"],
  ): EvaluationError | undefined {
    return currentRun.errors.find(
      (item) => item.predicted === predicted && item.actual === actual,
    );
  }
  return (
    <AppShell>
      <div className="workflow-page">
        <section
          className="evaluation-workbench"
          aria-labelledby="evaluation-title"
        >
          <header className="page-heading">
            <div className="title-with-meta">
              <h1 id="evaluation-title" className="sr-only">
                评测质量
              </h1>
              <span className="page-meta">
                {`${currentRun.id} · ${currentRun.algorithmVersion} · ${currentRun.datasetVersion}`}
              </span>
            </div>
          </header>

          <div className="evaluation-layout">
            <aside className="evaluation-dataset-list" aria-label="评测数据集">
              <h2>
                <Database aria-hidden size={14} /> 数据集
              </h2>
              <ul>
                {datasets.map((ds) => (
                  <li
                    className={`evaluation-dataset-item ${
                      ds.id === currentRun.dataset ? "is-active" : ""
                    }`}
                    key={ds.id}
                  >
                    <strong>{ds.name}</strong>
                    <span className="evaluation-dataset-samples">{`${ds.samples} 样本`}</span>
                    <span className="evaluation-dataset-version">
                      {ds.jobVersion}
                    </span>
                  </li>
                ))}
              </ul>
            </aside>

            <div className="evaluation-detail">
              <section className="evaluation-metrics-card">
                <SectionHeader
                  meta={`${currentRun.metrics.length} 项`}
                  title="运行指标"
                />
                <div className="evaluation-metric-grid">
                  {currentRun.metrics.map((m) => (
                    <div className="evaluation-metric" key={m.key}>
                      <span>{m.label}</span>
                      <Progress
                        percent={Math.round(m.value * 100)}
                        status={metricTone(m.value)}
                      />
                    </div>
                  ))}
                </div>
              </section>

              <section className="evaluation-error-list">
                <SectionHeader
                  meta={`${summary.errors} 条 · ${currentRun.errors.length} 类`}
                  title="预测偏差"
                />
                <p className="evaluation-error-summary">
                  {`${summary.total} 次回测中，${summary.hits} 次判断正确；命中率 ${Math.round(summary.accuracy * 1000) / 10}%，平稳基线 ${Math.round(summary.baselineAccuracy * 1000) / 10}%。`}
                </p>

                <div className="evaluation-error-content">
                  <div>
                    <h3>判断结果矩阵</h3>
                    <p className="evaluation-matrix-help">
                      纵向为实际结果，横向为预测结果。点击偏差数字查看案例。
                    </p>
                    <div className="evaluation-matrix-wrap">
                      <table className="evaluation-matrix">
                        <thead>
                          <tr>
                            <th scope="col">实际 \ 预测</th>
                            {DIRECTIONS.map((direction) => (
                              <th key={direction} scope="col">
                                {DIRECTION_LABELS[direction]}
                              </th>
                            ))}
                          </tr>
                        </thead>
                        <tbody>
                          {DIRECTIONS.map((actual) => (
                            <tr key={actual}>
                              <th scope="row">{DIRECTION_LABELS[actual]}</th>
                              {DIRECTIONS.map((predicted) => {
                                const error = matrixError(predicted, actual);
                                const count = matrixCount(predicted, actual);
                                const isHit = predicted === actual;
                                return (
                                  <td
                                    className={isHit ? "is-hit" : "is-error"}
                                    key={predicted}
                                  >
                                    {error ? (
                                      <button
                                        aria-label={`${error.label}，${count} 条`}
                                        onClick={() => setSelectedError(error)}
                                        type="button"
                                      >
                                        {count}
                                      </button>
                                    ) : (
                                      <span>{count}</span>
                                    )}
                                  </td>
                                );
                              })}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>

                  <div className="evaluation-review-list">
                    <h3>需优先复盘</h3>
                    <ul>
                      {currentRun.errors.map((err) => {
                        const severity = SEVERITY_META[err.severity];
                        return (
                          <li key={err.id}>
                            <button
                              onClick={() => setSelectedError(err)}
                              type="button"
                            >
                              <span className="evaluation-review-copy">
                                <strong>{err.label}</strong>
                                <span>
                                  {`${err.categoryLabel} · ${err.count} 条 · 占偏差 ${Math.round(err.share * 100)}%`}
                                </span>
                              </span>
                              <Tag color={severity.color}>{severity.label}</Tag>
                              <ArrowRight aria-hidden size={16} />
                            </button>
                          </li>
                        );
                      })}
                    </ul>
                  </div>
                </div>
              </section>
            </div>
          </div>
        </section>
        {extra}
      </div>
      <Drawer
        onClose={() => setSelectedError(null)}
        open={selectedError !== null}
        size="large"
        title={selectedError?.label ?? "偏差案例"}
      >
        {selectedError ? (
          <ErrorCaseDrawer error={selectedError} records={selectedCases} />
        ) : null}
      </Drawer>
    </AppShell>
  );
}

function ErrorCaseDrawer({
  error,
  records,
}: {
  error: EvaluationError;
  records: EvaluationCase[];
}) {
  const severity = SEVERITY_META[error.severity];
  return (
    <div className="evaluation-case-drawer">
      <div className="evaluation-case-intro">
        <Tag color={severity.color}>{severity.label}</Tag>
        <strong>{`${records.length} 条回测记录`}</strong>
        <span>{error.categoryLabel}</span>
      </div>
      <div className="evaluation-case-list">
        {records.map((record) => (
          <article key={record.id}>
            <header>
              <strong>{record.skillLabel}</strong>
              <time>{record.asOf}</time>
            </header>
            <p className="evaluation-case-direction">
              <span>{`预测${DIRECTION_LABELS[record.predicted]}`}</span>
              <ArrowRight aria-hidden size={15} />
              <strong>{`实际${DIRECTION_LABELS[record.actual]}`}</strong>
            </p>
            <dl>
              <div>
                <dt>置信度</dt>
                <dd>{`${Math.round(record.confidence * 100)}%`}</dd>
              </div>
              <div>
                <dt>前期信号</dt>
                <dd>{record.prior}</dd>
              </div>
              <div>
                <dt>近期信号</dt>
                <dd>{record.recent}</dd>
              </div>
            </dl>
            <details>
              <summary>处理信息</summary>
              <p>{`能力域 ${record.skillId} · 规则版本 ${record.ruleVersion}`}</p>
            </details>
          </article>
        ))}
      </div>
    </div>
  );
}
