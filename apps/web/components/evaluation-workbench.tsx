"use client";

import {
  ArrowSquareOut,
  Database,
  Warning,
} from "@phosphor-icons/react";
import { Button, Progress, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/workflow-ui";

// ponytail: 后端 B-T4 未开始；契约里也没有 EvaluationMetrics；
// 数据全部 inline 在组件内，不抽 lib/evaluation.ts。

type EvaluationDataset = {
  id: string;
  name: string;
  samples: number;
  jobVersion: string;
};

type EvaluationMetric = {
  key: string;
  label: string;
  value: number;
  hint?: string;
};

type ErrorCase = {
  id: string;
  skill: string;
  reason: string;
  priority: "high" | "medium";
};

const datasets: EvaluationDataset[] = [
  { id: "ds-a", name: "JD-AI 应用工程师 30", samples: 30, jobVersion: "v1.5" },
  { id: "ds-b", name: "JD-AI 应用工程师 22", samples: 22, jobVersion: "v1.4" },
  { id: "ds-c", name: "日报事实抽取 697", samples: 697, jobVersion: "temporal-v1" },
  { id: "ds-d", name: "回测 8 月", samples: 31, jobVersion: "backtest-2026-08" },
];

const currentRun = {
  id: "RUN-0825-001",
  dataset: "ds-a",
  algorithmVersion: "match-v0.1",
  datasetVersion: "2026-08-25",
  status: "REVIEWING" as const,
  metrics: [
    { key: "precision", label: "命中率", value: 0.61, hint: "正确判定 / 总判定" },
    { key: "recall", label: "召回率", value: 0.74 },
    { key: "confidence", label: "置信度", value: 0.84 },
  ] satisfies EvaluationMetric[],
  errors: [
    {
      id: "err-1",
      skill: "cap_04.MCP",
      reason: "召回低：18 个招聘 JD 漏识别",
      priority: "high" as const,
    },
    {
      id: "err-2",
      skill: "cap_05.图像生成",
      reason: "误判：把「文生图」匹配成「图像生成」但缺少 inpainting 关键词",
      priority: "medium" as const,
    },
    {
      id: "err-3",
      skill: "cap_06.检索评测",
      reason: "标签冲突：同时命中「检索质量评估」和「检索质量评估集」两个不同 alias",
      priority: "medium" as const,
    },
  ] satisfies ErrorCase[],
};

const pendingReview = {
  title: "回测 RUN-0825-001 待复盘",
  description: "1 个错误案例待人工审核（err-1 召回低）",
  href: "/jobs",
};

function metricTone(value: number): "success" | "normal" {
  return value >= 0.7 ? "success" : "normal";
}

function priorityLabel(priority: "high" | "medium"): string {
  return priority === "high" ? "优先" : "补强";
}

export function EvaluationWorkbench() {
  return (
    <AppShell>
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
    </AppShell>
  );
}