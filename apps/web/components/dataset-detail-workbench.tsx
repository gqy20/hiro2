"use client";

import Link from "next/link";
import { ArrowLeft } from "@phosphor-icons/react";
import { Button, Descriptions, Empty, Table, Tabs, Tag } from "antd";

import { ResumeArchiveBrowser } from "@/components/resume-archive-browser";
import type {
  DatasetDetail,
  DatasetSource,
  DatasetVersion,
} from "@/lib/datasets";
import type { ResumeArchiveItem } from "@/lib/resume-archive";

function formatNumber(value: number): string {
  return value.toLocaleString("zh-CN");
}

function usageText(datasetId: string): string {
  return (
    {
      jd: "岗位发现、岗位更新、能力图谱和人岗诊断",
      temporal: "趋势洞察、岗位影响建议和预测复盘",
      capability: "岗位版本、能力图谱和匹配规则",
      evidence: "审核任务、岗位版本、趋势结论和诊断解释",
      resumes: "候选人画像、人岗诊断和求职材料",
      evaluation: "评测质量、错误分析和规则迭代",
    }[datasetId] ?? "内部数据处理与质量治理"
  );
}

export function DatasetDetailWorkbench({
  detail,
  defaultTab,
  resumes,
  mockMode,
}: {
  detail: DatasetDetail;
  defaultTab?: string;
  resumes: ResumeArchiveItem[];
  mockMode: boolean;
}) {
  const dataset = detail.dataset;
  const latest = detail.versions[0];
  const tab = [
    "overview",
    "versions",
    "lineage",
    "quality",
    "records",
  ].includes(defaultTab ?? "")
    ? defaultTab
    : "overview";

  return (
    <section className="dataset-record" aria-labelledby="dataset-record-title">
      <header className="dataset-record-header">
        <div>
          <Link href="/data/assets">
            <ArrowLeft aria-hidden size={16} /> 数据资产
          </Link>
          <h1 id="dataset-record-title">{dataset.name}</h1>
          <span>{dataset.source}</span>
        </div>
        <div className="dataset-record-status">
          <Tag>{dataset.status}</Tag>
          <code>{dataset.version}</code>
        </div>
      </header>

      <Tabs
        className="dataset-record-tabs"
        defaultActiveKey={tab}
        items={[
          {
            key: "overview",
            label: "概览",
            children: (
              <div className="dataset-record-pane dataset-overview-pane">
                <section>
                  <h2>当前口径</h2>
                  <strong className="dataset-primary-count">
                    {formatNumber(dataset.records)}
                  </strong>
                  <span>{dataset.count_scope}</span>
                  <div className="dataset-stage-line">
                    {dataset.stage_counts.map((item) => (
                      <div key={item.stage}>
                        <span>{item.label}</span>
                        <strong>{formatNumber(item.count)}</strong>
                      </div>
                    ))}
                  </div>
                </section>
                <section>
                  <h2>当前状态</h2>
                  <p>
                    {dataset.valid_records === dataset.records
                      ? "当前登记记录全部有效。"
                      : `${formatNumber(dataset.records - dataset.valid_records)} 条记录仍待处理。`}
                  </p>
                  <p>{`主要用于${usageText(dataset.id)}。`}</p>
                </section>
              </div>
            ),
          },
          {
            key: "versions",
            label: `版本 ${detail.versions.length}`,
            children: <VersionPane versions={detail.versions} />,
          },
          {
            key: "lineage",
            label: "血缘",
            children: (
              <LineagePane
                datasetId={dataset.id}
                runId={latest?.run_id ?? ""}
                sources={dataset.sources ?? []}
              />
            ),
          },
          {
            key: "quality",
            label: "字段质量",
            children: (
              <div className="dataset-record-pane">
                <Descriptions bordered column={1} size="small">
                  <Descriptions.Item label="登记质量">
                    {`${dataset.quality}%`}
                  </Descriptions.Item>
                  <Descriptions.Item label="数据格式">
                    {dataset.formats.join("、")}
                  </Descriptions.Item>
                  <Descriptions.Item label="Manifest 哈希">
                    <code>{latest?.manifest_hash || "未登记"}</code>
                  </Descriptions.Item>
                </Descriptions>
                <p className="dataset-pending-note">
                  字段完整率、唯一值和异常样本需要数据字典接口后才能展示；当前不使用登记质量推断字段质量。
                </p>
              </div>
            ),
          },
          {
            key: "records",
            label: `记录 ${formatNumber(dataset.records)}`,
            children: (
              <RecordPane
                datasetId={dataset.id}
                mockMode={mockMode}
                resumes={resumes}
              />
            ),
          },
        ]}
      />
    </section>
  );
}

function VersionPane({ versions }: { versions: DatasetVersion[] }) {
  return (
    <div className="dataset-record-pane">
      <Table<DatasetVersion>
        columns={[
          { title: "版本", dataIndex: "version" },
          { title: "状态", dataIndex: "status" },
          {
            title: "记录",
            dataIndex: "records",
            align: "right",
            render: formatNumber,
          },
          {
            title: "有效",
            dataIndex: "valid_records",
            align: "right",
            render: formatNumber,
          },
          {
            title: "待处理",
            dataIndex: "pending_records",
            align: "right",
            render: formatNumber,
          },
          {
            title: "导入时间",
            dataIndex: "imported_at",
            render: (value) =>
              value ? String(value).slice(0, 16).replace("T", " ") : "—",
          },
          {
            title: "运行",
            dataIndex: "run_id",
            render: (value) =>
              value ? (
                <Link href={`/data/pipeline?run_id=${value}`}>查看运行</Link>
              ) : (
                "—"
              ),
          },
        ]}
        dataSource={versions}
        pagination={false}
        rowKey="version"
        scroll={{ x: 900 }}
        size="middle"
      />
    </div>
  );
}

function LineagePane({
  datasetId,
  sources,
  runId,
}: {
  datasetId: string;
  sources: DatasetSource[];
  runId: string;
}) {
  return (
    <div className="dataset-record-pane dataset-lineage-pane">
      <div className="dataset-lineage-flow">
        <div>
          <span>来源通道</span>
          <strong>{sources.length || "派生数据"}</strong>
        </div>
        <i aria-hidden>→</i>
        <div>
          <span>数据集</span>
          <strong>{datasetId}</strong>
        </div>
        <i aria-hidden>→</i>
        <div>
          <span>最近运行</span>
          <strong>{runId || "未登记"}</strong>
        </div>
        <i aria-hidden>→</i>
        <div>
          <span>下游</span>
          <strong>{usageText(datasetId)}</strong>
        </div>
      </div>
      {sources.length ? (
        <Table<DatasetSource>
          columns={[
            { title: "来源通道", dataIndex: "id" },
            { title: "类型", dataIndex: "type" },
            { title: "模式", dataIndex: "ingestion_mode" },
            {
              title: "时间范围",
              dataIndex: "time_range",
              render: (value: string[]) => value.join(" ～ "),
            },
            { title: "使用许可", dataIndex: "license" },
          ]}
          dataSource={sources}
          pagination={false}
          rowKey="id"
          scroll={{ x: 900 }}
          size="small"
        />
      ) : null}
    </div>
  );
}

function RecordPane({
  datasetId,
  resumes,
  mockMode,
}: {
  datasetId: string;
  resumes: ResumeArchiveItem[];
  mockMode: boolean;
}) {
  if (datasetId === "resumes") {
    return <ResumeArchiveBrowser archive={resumes} mockMode={mockMode} />;
  }
  const target = {
    evidence: ["/tasks?view=evidence", "打开证据库"],
    temporal: ["/temporal", "打开趋势洞察"],
    evaluation: ["/tasks?view=tasks", "打开评测任务"],
  }[datasetId];
  return (
    <div className="dataset-record-pane dataset-record-empty">
      <Empty description="该数据集需要使用专属字段浏览器，不能使用通用记录表格。" />
      {target ? <Button href={target[0]}>{target[1]}</Button> : null}
    </div>
  );
}
