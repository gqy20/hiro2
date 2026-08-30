"use client";

import { useState, type ReactNode } from "react";
import { ArrowRight, Database } from "@phosphor-icons/react";
import { Drawer, Progress, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/workflow-ui";
import type { EvaluationOverview } from "@/lib/evaluation";

type EvaluationError = EvaluationOverview["errors"][number];
type EvaluationCase = EvaluationOverview["cases"][number];
type SampleEvaluation = EvaluationOverview["sampleEvaluations"][number];
type SampleCase = SampleEvaluation["cases"][number];

const DIRECTIONS = ["up", "flat", "down"] as const;
const DIRECTION_LABELS = { up: "上升", flat: "平稳", down: "下降" };
const SEVERITY_META = {
  critical: { color: "red", label: "严重偏差" },
  high: { color: "orange", label: "趋势漏判" },
  medium: { color: "blue", label: "趋势误报" },
} as const;

function metricTone(value: number): "success" | "normal" {
  return value >= 0.7 ? "success" : "normal";
}

function isSampleError(item: SampleCase): boolean {
  return item.decision === "MODIFY" || item.decision === "REJECT";
}

export function EvaluationWorkbench({
  overview,
  extra,
}: {
  overview: EvaluationOverview;
  extra?: ReactNode;
}) {
  const datasets = overview.datasets;
  const sampleEvaluations = overview.sampleEvaluations ?? [];
  const [activeDatasetId, setActiveDatasetId] = useState(
    datasets[0]?.id ?? "trend",
  );
  const [selectedError, setSelectedError] = useState<EvaluationError | null>(
    null,
  );
  const [selectedSample, setSelectedSample] = useState<SampleCase | null>(null);
  const activeDataset =
    datasets.find((item) => item.id === activeDatasetId) ?? datasets[0];
  const activeSample = sampleEvaluations.find(
    (item) => item.id === activeDatasetId,
  );
  const trendCases = overview.cases ?? [];
  const selectedTrendCases = selectedError
    ? trendCases.filter(
        (item) =>
          !item.hit &&
          item.predicted === selectedError.predicted &&
          item.actual === selectedError.actual,
      )
    : [];
  const pageMeta = activeSample
    ? `${activeSample.name} · ${activeDataset?.jobVersion ?? ""}`
    : `${overview.run.id} · ${overview.run.algorithmVersion} · ${overview.run.datasetVersion}`;

  function selectDataset(id: string) {
    setActiveDatasetId(id);
    setSelectedError(null);
    setSelectedSample(null);
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
              <span className="page-meta">{pageMeta}</span>
            </div>
          </header>

          <div className="evaluation-layout">
            <aside className="evaluation-dataset-list" aria-label="评测对象">
              <h2>
                <Database aria-hidden size={14} /> 评测对象
              </h2>
              <ul>
                {datasets.map((dataset) => (
                  <li
                    className={`evaluation-dataset-item ${
                      dataset.id === activeDatasetId ? "is-active" : ""
                    }`}
                    key={dataset.id}
                  >
                    <button
                      aria-pressed={dataset.id === activeDatasetId}
                      onClick={() => selectDataset(dataset.id)}
                      type="button"
                    >
                      <strong>{dataset.name}</strong>
                      <span className="evaluation-dataset-samples">
                        {`${dataset.samples} 样本`}
                      </span>
                      <span className="evaluation-dataset-version">
                        {dataset.jobVersion}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </aside>

            <div className="evaluation-detail">
              {activeSample ? (
                <SampleEvaluationPanel
                  evaluation={activeSample}
                  key={activeSample.id}
                  onSelect={setSelectedSample}
                />
              ) : (
                <TrendEvaluationPanel
                  overview={overview}
                  onSelectError={setSelectedError}
                />
              )}
            </div>
          </div>
        </section>
        {extra}
      </div>

      <Drawer
        onClose={() => setSelectedSample(null)}
        open={selectedSample !== null}
        size="large"
        title={selectedSample?.title ?? "评测案例"}
      >
        {selectedSample ? <SampleCaseDrawer record={selectedSample} /> : null}
      </Drawer>
      <Drawer
        onClose={() => setSelectedError(null)}
        open={selectedError !== null}
        size="large"
        title={selectedError?.label ?? "偏差案例"}
      >
        {selectedError ? (
          <ErrorCaseDrawer error={selectedError} records={selectedTrendCases} />
        ) : null}
      </Drawer>
    </AppShell>
  );
}

function SampleEvaluationPanel({
  evaluation,
  onSelect,
}: {
  evaluation: SampleEvaluation;
  onSelect: (record: SampleCase) => void;
}) {
  const [filter, setFilter] = useState<"errors" | "all">(
    evaluation.summary.errors > 0 ? "errors" : "all",
  );
  const visibleCases =
    filter === "errors"
      ? evaluation.cases.filter(isSampleError)
      : evaluation.cases;

  return (
    <>
      <section className="evaluation-sample-overview">
        <SectionHeader
          meta={`${evaluation.summary.reviewed} / ${evaluation.summary.total} 已评`}
          title={evaluation.name}
        />
        <p>{evaluation.description}</p>
        <div className="evaluation-sample-summary" aria-label="评测结果">
          <div>
            <span>准确率</span>
            <strong>{`${Math.round(evaluation.summary.accuracy * 100)}%`}</strong>
          </div>
          <div>
            <span>判断一致</span>
            <strong>{evaluation.summary.correct}</strong>
          </div>
          <div>
            <span>需复盘</span>
            <strong>{evaluation.summary.errors}</strong>
          </div>
          <Progress
            percent={Math.round(evaluation.summary.accuracy * 100)}
            showInfo={false}
            status={metricTone(evaluation.summary.accuracy)}
          />
        </div>
      </section>

      <section className="evaluation-sample-cases">
        <div className="evaluation-case-heading">
          <SectionHeader
            meta={`${visibleCases.length} 条`}
            title={evaluation.summary.errors > 0 ? "案例复盘" : "样本记录"}
          />
          {evaluation.summary.errors > 0 ? (
            <div className="evaluation-case-filter" aria-label="案例范围">
              <button
                aria-pressed={filter === "errors"}
                onClick={() => setFilter("errors")}
                type="button"
              >
                {`需复盘 ${evaluation.summary.errors}`}
              </button>
              <button
                aria-pressed={filter === "all"}
                onClick={() => setFilter("all")}
                type="button"
              >
                {`全部 ${evaluation.summary.total}`}
              </button>
            </div>
          ) : null}
        </div>
        <ul className="evaluation-sample-list">
          {visibleCases.map((record) => {
            const error = isSampleError(record);
            return (
              <li key={record.id}>
                <button onClick={() => onSelect(record)} type="button">
                  <span className="evaluation-sample-title">
                    <strong>{record.title}</strong>
                    <span>{record.systemResult}</span>
                  </span>
                  <Tag color={error ? "red" : "green"}>
                    {error ? "需复盘" : "判断一致"}
                  </Tag>
                  <ArrowRight aria-hidden size={16} />
                </button>
              </li>
            );
          })}
        </ul>
      </section>
    </>
  );
}

function TrendEvaluationPanel({
  overview,
  onSelectError,
}: {
  overview: EvaluationOverview;
  onSelectError: (error: EvaluationError) => void;
}) {
  const cases = overview.cases ?? [];
  const summary = overview.summary;

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
    return overview.errors.find(
      (item) => item.predicted === predicted && item.actual === actual,
    );
  }

  return (
    <>
      <section className="evaluation-metrics-card">
        <SectionHeader meta="2 项" title="运行指标" />
        <div className="evaluation-metric-grid">
          {overview.metrics
            .filter(
              (metric) =>
                metric.key === "accuracy" || metric.key === "baseline",
            )
            .map((metric) => (
              <div className="evaluation-metric" key={metric.key}>
                <span>{metric.label}</span>
                <Progress
                  percent={Math.round(metric.value * 100)}
                  status={metricTone(metric.value)}
                />
              </div>
            ))}
        </div>
      </section>

      <section className="evaluation-error-list">
        <SectionHeader
          meta={`${summary.errors} 条 · ${overview.errors.length} 类`}
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
                        return (
                          <td
                            className={
                              predicted === actual ? "is-hit" : "is-error"
                            }
                            key={predicted}
                          >
                            {error ? (
                              <button
                                aria-label={`${error.label}，${count} 条`}
                                onClick={() => onSelectError(error)}
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
              {overview.errors.map((error) => {
                const severity = SEVERITY_META[error.severity];
                return (
                  <li key={error.id}>
                    <button onClick={() => onSelectError(error)} type="button">
                      <span className="evaluation-review-copy">
                        <strong>{error.label}</strong>
                        <span>
                          {`${error.categoryLabel} · ${error.count} 条 · 占偏差 ${Math.round(error.share * 100)}%`}
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
    </>
  );
}

function SampleCaseDrawer({ record }: { record: SampleCase }) {
  const error = isSampleError(record);
  return (
    <div className="evaluation-sample-drawer">
      <div className="evaluation-case-intro">
        <Tag color={error ? "red" : "green"}>
          {error ? "需复盘" : "判断一致"}
        </Tag>
        <strong>{record.systemResult}</strong>
        {record.date ? <span>{record.date}</span> : null}
      </div>
      <section>
        <h3>系统判断</h3>
        <p>{record.systemResult}</p>
        <p>{record.detail}</p>
      </section>
      <section>
        <h3>复盘结论</h3>
        {record.expectedResult ? (
          <strong>{record.expectedResult}</strong>
        ) : null}
        <p>{record.rationale || "系统判断与评测结论一致。"}</p>
      </section>
      <details>
        <summary>处理信息</summary>
        <p>{`来源记录：${record.sourceId}`}</p>
        <p>{`评测任务：${record.id}`}</p>
        <p>{`审核人：${record.reviewer || "未登记"}`}</p>
      </details>
    </div>
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
