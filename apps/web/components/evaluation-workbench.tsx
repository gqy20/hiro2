"use client";

import {
  ArrowSquareOut,
  Database,
  Warning,
} from "@phosphor-icons/react";
import { Button, Progress, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/workflow-ui";
import { WorkflowContext } from "@/components/workflow-context";
import type { EvaluationOverview } from "@/lib/evaluation";

// ponytail: 后端 B-T4 未开始；契约里也没有 EvaluationMetrics；
// 数据全部 inline 在组件内，不抽 lib/evaluation.ts。

function metricTone(value: number): "success" | "normal" {
  return value >= 0.7 ? "success" : "normal";
}

function priorityLabel(priority: "high" | "medium"): string {
  return priority === "high" ? "优先" : "补强";
}

export function EvaluationWorkbench({ overview }: { overview: EvaluationOverview }) {
  const currentRun = {
    ...overview.run,
    dataset: overview.datasets[0]?.id ?? "",
    metrics: overview.metrics,
    errors: overview.errors,
  };
  const datasets = overview.datasets;
  const pendingReview = overview.pending;
  return (
    <AppShell>
      <div className="workflow-page">
      <WorkflowContext eyebrow="审核工作区" title="评测中心" stage="复盘系统判断" next="打开错误案例" />
      <section className="evaluation-workbench" aria-labelledby="evaluation-title">
        <header className="page-heading">
          <div className="title-with-meta">
            <h1 id="evaluation-title">评测中心</h1>
            <span className="page-meta">
              {`${currentRun.id} · ${currentRun.algorithmVersion} · ${currentRun.datasetVersion}`}
            </span>
          </div>
          <Tag>{currentRun.status}</Tag>
        </header>

        <div className="evaluation-layout">
          <aside
            className="evaluation-dataset-list"
            aria-label="评测数据集"
          >
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
                  <span>
                    {`${ds.samples} 样本 · ${ds.jobVersion}`}
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
                    {m.hint ? <small>{m.hint}</small> : null}
                  </div>
                ))}
              </div>
            </section>

            <section className="evaluation-error-list">
              <SectionHeader
                meta={`${currentRun.errors.length} 项`}
                title="错误案例"
              />
              <ul>
                {currentRun.errors.map((err) => (
                  <li className="evaluation-error-item" key={err.id}>
                    <div>
                      <strong>{err.skill}</strong>
                      <p>{err.reason}</p>
                    </div>
                    <Tag
                      color={
                        err.priority === "high" ? "red" : "blue"
                      }
                    >
                      {priorityLabel(err.priority)}
                    </Tag>
                  </li>
                ))}
              </ul>
            </section>
          </div>

          <aside className="evaluation-pending" aria-label="待复盘">
            <h2>
              <Warning aria-hidden size={14} /> 待复盘
            </h2>
            <article>
              <strong>{pendingReview.title}</strong>
              <p>{pendingReview.description}</p>
              <Button
                block
                href={pendingReview.href}
                icon={<ArrowSquareOut aria-hidden size={14} />}
                type="primary"
              >
                查看关联岗位
              </Button>
            </article>
          </aside>
        </div>
      </section>
      </div>
    </AppShell>
  );
}
