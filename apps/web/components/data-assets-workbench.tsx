"use client";

import { useMemo, useState } from "react";
import { ArrowLeft, ArrowSquareOut } from "@phosphor-icons/react";
import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Segmented,
  Spin,
  Table,
  Tabs,
  Tag,
} from "antd";

import { apiFetch } from "@/lib/api/client";
import type {
  DatasetDetail,
  DatasetItem,
  DatasetOverview,
  DatasetSource,
  DatasetSourceDetail,
  DatasetVersion,
} from "@/lib/datasets";

type View = "datasets" | "sources";
type SourceRow = DatasetSource & {
  datasetId: string;
  datasetName: string;
  datasetVersion: string;
};

const TYPE_LABELS: Record<string, string> = {
  expert_matrix: "专家矩阵",
  government_policy: "政府政策",
  occupational_database: "职业数据库",
  academic_dataset: "学术数据集",
  academic_preprint: "预印本论文",
  job_board: "招聘平台",
  web_archive: "网页存档",
  employer_site: "企业官网",
  occupation_standard: "职业标准",
  industry_media: "产业媒体",
  rss_direct: "RSS 订阅",
  package_registry: "包仓库",
};

function formatNumber(value: number): string {
  return value.toLocaleString("zh-CN");
}

function mockDatasetDetail(dataset: DatasetItem): DatasetDetail {
  return {
    dataset,
    versions: [
      {
        dataset_id: dataset.id,
        version: dataset.version,
        status: dataset.status,
        records: dataset.records,
        valid_records: dataset.valid_records,
        pending_records: Math.max(dataset.records - dataset.valid_records, 0),
        quality: dataset.quality,
        manifest_hash: "",
        manifest: {},
        run_id: "",
        imported_at: dataset.updated_at,
      },
    ],
  };
}

export function DataAssetsWorkbench({
  overview,
  mockMode,
}: {
  overview: DatasetOverview;
  mockMode: boolean;
}) {
  const [view, setView] = useState<View>("datasets");
  const [datasetDetail, setDatasetDetail] = useState<DatasetDetail | null>(
    null,
  );
  const [sourceDetail, setSourceDetail] = useState<DatasetSourceDetail | null>(
    null,
  );
  const [loading, setLoading] = useState(false);

  const sourceRows = useMemo<SourceRow[]>(
    () =>
      overview.datasets.flatMap((dataset) =>
        (dataset.sources ?? []).map((source) => ({
          ...source,
          datasetId: dataset.id,
          datasetName: dataset.name,
          datasetVersion: dataset.version,
        })),
      ),
    [overview.datasets],
  );

  async function openDataset(dataset: DatasetItem) {
    setSourceDetail(null);
    if (mockMode) {
      setDatasetDetail(mockDatasetDetail(dataset));
      return;
    }
    setLoading(true);
    try {
      setDatasetDetail(
        await apiFetch<DatasetDetail>(
          `/datasets/${encodeURIComponent(dataset.id)}`,
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  async function openSource(row: SourceRow) {
    if (mockMode) {
      setSourceDetail({
        dataset_id: row.datasetId,
        dataset_version: row.datasetVersion,
        source: row,
        stats: {
          evidence_count: 0,
          reviewed_evidence_count: null,
          average_quality: null,
          latest_evidence_at: "",
          claim_types: {},
          attribution: "unavailable",
          attribution_note: "离线模式不提供来源统计。",
        },
      });
      return;
    }
    setLoading(true);
    try {
      setSourceDetail(
        await apiFetch<DatasetSourceDetail>(
          `/datasets/${encodeURIComponent(row.datasetId)}/sources/${encodeURIComponent(row.id)}`,
        ),
      );
    } finally {
      setLoading(false);
    }
  }

  const currentDataset = datasetDetail?.dataset;
  return (
    <section className="data-assets" aria-labelledby="data-assets-title">
      <header className="data-assets-toolbar">
        <div>
          <h1 id="data-assets-title" className="sr-only">
            数据资产
          </h1>
          <strong>{`${overview.total_datasets} 个数据集 · ${sourceRows.length} 个来源通道`}</strong>
          <span>{`${formatNumber(overview.total_records)} 条登记记录`}</span>
        </div>
        <Segmented
          aria-label="切换数据资产视图"
          onChange={(value) => setView(value as View)}
          options={[
            { label: "数据集", value: "datasets" },
            { label: "来源通道", value: "sources" },
          ]}
          value={view}
        />
      </header>

      {view === "datasets" ? (
        <Table<DatasetItem>
          columns={[
            {
              title: "数据集",
              dataIndex: "name",
              render: (_, item) => (
                <span className="data-assets-name">
                  <strong>{item.name}</strong>
                  <small>{item.source}</small>
                </span>
              ),
            },
            { title: "类型", dataIndex: "category", width: 130 },
            {
              title: "记录",
              dataIndex: "records",
              width: 120,
              align: "right",
              render: (_, item) => (
                <span className="data-assets-count">
                  <strong>{formatNumber(item.records)}</strong>
                  <small>{item.count_scope}</small>
                </span>
              ),
            },
            { title: "当前版本", dataIndex: "version", width: 180 },
            {
              title: "来源",
              width: 100,
              render: (_, item) => `${item.sources?.length ?? 0} 个`,
            },
            {
              title: "状态",
              dataIndex: "status",
              width: 110,
              render: (status) => <Tag>{String(status)}</Tag>,
            },
            {
              title: "最近更新",
              dataIndex: "updated_at",
              width: 130,
              render: (value) => (value ? String(value).slice(0, 10) : "—"),
            },
          ]}
          dataSource={overview.datasets}
          locale={{ emptyText: <Empty description="暂无数据集" /> }}
          onRow={(item) => ({
            onClick: () => void openDataset(item),
            onKeyDown: (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                void openDataset(item);
              }
            },
            tabIndex: 0,
          })}
          pagination={false}
          rowClassName="data-assets-row"
          rowKey="id"
          scroll={{ x: 980 }}
          size="middle"
        />
      ) : (
        <Table<SourceRow>
          columns={[
            { title: "来源通道", dataIndex: "id", width: 180 },
            {
              title: "类型",
              dataIndex: "type",
              width: 130,
              render: (value) => TYPE_LABELS[String(value)] ?? String(value),
            },
            { title: "所属数据集", dataIndex: "datasetName", width: 150 },
            {
              title: "采集模式",
              dataIndex: "ingestion_mode",
              width: 120,
              render: (value) => (value === "live" ? "实时采集" : "历史回填"),
            },
            {
              title: "时间范围",
              dataIndex: "time_range",
              width: 190,
              render: (value: string[]) => value.join(" ～ ") || "—",
            },
            { title: "使用许可", dataIndex: "license" },
          ]}
          dataSource={sourceRows}
          locale={{ emptyText: <Empty description="暂无来源通道" /> }}
          onRow={(item) => ({
            onClick: () => void openSource(item),
            onKeyDown: (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                void openSource(item);
              }
            },
            tabIndex: 0,
          })}
          pagination={{ pageSize: 20, showSizeChanger: false }}
          rowClassName="data-assets-row"
          rowKey={(item) => `${item.datasetId}:${item.id}`}
          scroll={{ x: 980 }}
          size="middle"
        />
      )}

      <Drawer
        onClose={() => {
          setDatasetDetail(null);
          setSourceDetail(null);
        }}
        open={Boolean(datasetDetail || sourceDetail || loading)}
        size="large"
        title={
          sourceDetail
            ? sourceDetail.source.id
            : (currentDataset?.name ?? "数据资产详情")
        }
      >
        {loading ? <Spin description="正在读取详情" /> : null}
        {!loading && sourceDetail ? (
          <SourceAssetDetail
            detail={sourceDetail}
            onBack={() => setSourceDetail(null)}
          />
        ) : null}
        {!loading && datasetDetail ? (
          <DatasetAssetDetail detail={datasetDetail} onSource={openSource} />
        ) : null}
      </Drawer>
    </section>
  );
}

function DatasetAssetDetail({
  detail,
  onSource,
}: {
  detail: DatasetDetail;
  onSource: (source: SourceRow) => Promise<void>;
}) {
  const dataset = detail.dataset;
  const latest = detail.versions[0];
  return (
    <div className="data-asset-detail">
      <div className="data-asset-summary">
        <Tag>{dataset.status}</Tag>
        <code>{dataset.version}</code>
        <span>
          {dataset.updated_at
            ? `更新于 ${dataset.updated_at.slice(0, 10)}`
            : ""}
        </span>
      </div>
      <Descriptions bordered column={2} size="small">
        <Descriptions.Item label="记录">
          {formatNumber(dataset.records)}
        </Descriptions.Item>
        <Descriptions.Item label="有效">
          {formatNumber(dataset.valid_records)}
        </Descriptions.Item>
        <Descriptions.Item label="质量">{`${dataset.quality}%`}</Descriptions.Item>
        <Descriptions.Item label="待处理">
          {formatNumber(Math.max(dataset.records - dataset.valid_records, 0))}
        </Descriptions.Item>
      </Descriptions>
      <div className="data-asset-stage-counts" aria-label="处理阶段数量">
        {dataset.stage_counts.map((item) => (
          <div key={item.stage}>
            <span>{item.label}</span>
            <strong>{formatNumber(item.count)}</strong>
          </div>
        ))}
      </div>
      <Tabs
        items={[
          {
            key: "overview",
            label: "概览",
            children: (
              <div className="data-asset-section">
                <h3>数据集说明</h3>
                <p>{dataset.source}</p>
                <h3>使用位置</h3>
                <p>岗位发现、岗位更新、能力图谱、人岗诊断和评测质量。</p>
                <Button href={`/data/assets/${dataset.id}`} type="primary">
                  打开完整档案
                </Button>
                {dataset.id === "evidence" ? (
                  <Button href="/tasks?view=evidence">浏览全部证据记录</Button>
                ) : null}
                {dataset.id === "temporal" ? (
                  <Button href="/temporal">查看趋势洞察</Button>
                ) : null}
              </div>
            ),
          },
          {
            key: "versions",
            label: `版本历史 ${detail.versions.length}`,
            children: <VersionTable versions={detail.versions} />,
          },
          {
            key: "sources",
            label: `来源 ${dataset.sources?.length ?? 0}`,
            children: (
              <ul className="data-asset-source-list">
                {(dataset.sources ?? []).map((source) => (
                  <li key={source.id}>
                    <button
                      onClick={() =>
                        void onSource({
                          ...source,
                          datasetId: dataset.id,
                          datasetName: dataset.name,
                          datasetVersion: dataset.version,
                        })
                      }
                      type="button"
                    >
                      <span>
                        <strong>{source.id}</strong>
                        <small>{TYPE_LABELS[source.type] ?? source.type}</small>
                      </span>
                      <ArrowSquareOut aria-hidden size={16} />
                    </button>
                  </li>
                ))}
              </ul>
            ),
          },
          {
            key: "technical",
            label: "技术信息",
            children: (
              <Descriptions bordered column={1} size="small">
                <Descriptions.Item label="格式">
                  {dataset.formats.join("、")}
                </Descriptions.Item>
                <Descriptions.Item label="Manifest 哈希">
                  <code>{latest?.manifest_hash || "未登记"}</code>
                </Descriptions.Item>
                <Descriptions.Item label="导入运行">
                  {latest?.run_id ? (
                    <Button
                      href={`/data/pipeline?run_id=${latest.run_id}`}
                      type="link"
                    >
                      {latest.run_id}
                    </Button>
                  ) : (
                    "未登记"
                  )}
                </Descriptions.Item>
                {Object.entries(latest?.manifest ?? {}).map(([key, value]) => (
                  <Descriptions.Item key={key} label={key}>
                    {String(value)}
                  </Descriptions.Item>
                ))}
              </Descriptions>
            ),
          },
        ]}
      />
    </div>
  );
}

function VersionTable({ versions }: { versions: DatasetVersion[] }) {
  return (
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
        { title: "质量", dataIndex: "quality", render: (value) => `${value}%` },
        {
          title: "导入时间",
          dataIndex: "imported_at",
          render: (value) =>
            value ? String(value).slice(0, 16).replace("T", " ") : "—",
        },
      ]}
      dataSource={versions}
      pagination={false}
      rowKey="version"
      size="small"
    />
  );
}

function SourceAssetDetail({
  detail,
  onBack,
}: {
  detail: DatasetSourceDetail;
  onBack: () => void;
}) {
  const { source, stats } = detail;
  return (
    <div className="data-asset-detail">
      <Button icon={<ArrowLeft aria-hidden />} onClick={onBack} type="text">
        返回数据集
      </Button>
      {stats.attribution === "unavailable" ? (
        <Alert
          title="通道统计暂不可精确归因"
          description={stats.attribution_note}
          showIcon
        />
      ) : null}
      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="所属数据集">
          {detail.dataset_id}
        </Descriptions.Item>
        <Descriptions.Item label="来源类型">
          {TYPE_LABELS[source.type] ?? source.type}
        </Descriptions.Item>
        <Descriptions.Item label="采集模式">
          {source.ingestion_mode === "live" ? "实时采集" : "历史回填"}
        </Descriptions.Item>
        <Descriptions.Item label="时间范围">
          {source.time_range.join(" ～ ") || "未登记"}
        </Descriptions.Item>
        <Descriptions.Item label="使用许可">
          {source.license || "未登记"}
        </Descriptions.Item>
        <Descriptions.Item label="相关证据">
          {stats.attribution === "exact"
            ? formatNumber(stats.evidence_count)
            : "—"}
        </Descriptions.Item>
        <Descriptions.Item label="平均质量">
          {stats.average_quality === null
            ? "尚未评估"
            : `${Math.round(stats.average_quality * 100)}%`}
        </Descriptions.Item>
      </Descriptions>
      <section className="data-asset-section">
        <h3>来源说明</h3>
        <p>{source.notes || "未登记来源说明。"}</p>
      </section>
      {stats.attribution === "exact" ? (
        <Button
          href={`/tasks?view=evidence&source_id=${encodeURIComponent(source.id)}`}
        >
          查看相关证据
        </Button>
      ) : null}
    </div>
  );
}
