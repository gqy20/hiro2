"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Button,
  DatePicker,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Select,
  Table,
  Tag,
} from "antd";

import { apiFetch, isMockMode } from "@/lib/api/client";
import type {
  EvidenceFacets,
  EvidenceSearchItem,
  EvidenceSearchResult,
} from "@/lib/evidence-search";

const CLAIM_LABELS: Record<string, string> = {
  trend_signal: "趋势信号",
  job_requirement: "岗位要求",
  expert_baseline: "专家基线",
};

const STATUS_LABELS: Record<string, string> = {
  PENDING: "待审核",
  ACCEPTED: "已接受",
  MODIFIED: "已修改",
  REJECTED: "已拒绝",
};

const SOURCE_LABELS: Record<string, string> = {
  "wechat-mp": "AI 日报",
  bytedance: "字节跳动",
  alibaba: "阿里巴巴",
  tencent: "腾讯",
  meituan: "美团",
  xiaohongshu: "小红书",
  vivo: "vivo",
  anthropic: "Anthropic",
  "51job": "前程无忧",
  boss: "BOSS 直聘",
  "capability-matrix": "岗位能力矩阵",
};

function sourceLabel(value: string): string {
  if (SOURCE_LABELS[value]) return SOURCE_LABELS[value];
  if (value.startsWith("gh-")) {
    return `${value.slice(3).replaceAll("-", " ")} 招聘`;
  }
  return value;
}

function qualityMeta(value: number): { label: string; color: string } {
  if (value >= 0.85) return { label: "高", color: "green" };
  if (value >= 0.7) return { label: "中", color: "gold" };
  return { label: "低", color: "red" };
}

export function EvidenceBrowser({
  initial,
  initialSource = "",
  facets,
}: {
  initial: EvidenceSearchResult;
  initialSource?: string;
  facets: EvidenceFacets;
}) {
  const [result, setResult] = useState(initial);
  const [sourceId, setSourceId] = useState(initialSource);
  const [claimType, setClaimType] = useState("");
  const [reviewStatus, setReviewStatus] = useState("");
  const [query, setQuery] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<EvidenceSearchItem | null>(null);

  const search = useCallback(
    async (page = 1) => {
      if (isMockMode()) return;
      setLoading(true);
      try {
        const params = new URLSearchParams({
          limit: "50",
          offset: String((page - 1) * 50),
        });
        if (sourceId) params.set("source_id", sourceId);
        if (claimType) params.set("claim_type", claimType);
        if (reviewStatus) params.set("review_status", reviewStatus);
        if (dateFrom) params.set("date_from", dateFrom);
        if (dateTo) params.set("date_to", dateTo);
        if (query.trim()) params.set("q", query.trim());
        setResult(await apiFetch<EvidenceSearchResult>(`/evidence?${params}`));
      } finally {
        setLoading(false);
      }
    },
    [claimType, dateFrom, dateTo, query, reviewStatus, sourceId],
  );

  useEffect(() => {
    const timer = window.setTimeout(() => void search(1), 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  return (
    <section className="evidence-browser" aria-label="证据库">
      <div className="evidence-browser-toolbar">
        <div>
          <strong>{`${result.total.toLocaleString("zh-CN")} 条证据`}</strong>
          <span>每页 50 条，筛选由后端执行</span>
        </div>
        <Select
          allowClear
          aria-label="筛选证据来源"
          onChange={(value) => setSourceId(value ?? "")}
          optionFilterProp="label"
          options={facets.sources.map((source) => ({
            label: `${sourceLabel(source.value)} · ${source.count.toLocaleString("zh-CN")}`,
            value: source.value,
          }))}
          placeholder="全部来源"
          showSearch
          value={sourceId || undefined}
        />
        <Select
          aria-label="证据类型"
          onChange={setClaimType}
          options={[
            { label: "全部类型", value: "" },
            ...Object.entries(CLAIM_LABELS).map(([value, label]) => ({
              value,
              label,
            })),
          ]}
          value={claimType}
        />
        <Select
          aria-label="审核状态"
          onChange={setReviewStatus}
          options={[
            { label: "全部状态", value: "" },
            ...Object.entries(STATUS_LABELS).map(([value, label]) => ({
              value,
              label,
            })),
          ]}
          value={reviewStatus}
        />
        <DatePicker.RangePicker
          aria-label="筛选发布时间范围"
          onChange={(_, values) => {
            setDateFrom(values[0]);
            setDateTo(values[1]);
          }}
          placeholder={["开始日期", "结束日期"]}
        />
        <Input
          allowClear
          aria-label="搜索证据"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索内容或证据 ID"
          value={query}
        />
      </div>
      <Table<EvidenceSearchItem>
        columns={[
          {
            title: "证据",
            dataIndex: "id",
            render: (_, item) => (
              <span className="evidence-browser-title">
                <strong>{item.excerpt || item.id}</strong>
              </span>
            ),
          },
          {
            title: "来源",
            dataIndex: "source",
            width: 150,
            render: (value) => sourceLabel(String(value)),
          },
          {
            title: "类型",
            dataIndex: "claimType",
            width: 120,
            render: (value) => CLAIM_LABELS[String(value)] ?? String(value),
          },
          {
            title: "时间",
            dataIndex: "publishedAt",
            width: 120,
            render: (value) => (value ? String(value).slice(0, 10) : "—"),
          },
          {
            title: "质量等级",
            dataIndex: "quality",
            width: 100,
            render: (value) => {
              const quality = Number(value);
              const meta = qualityMeta(quality);
              return (
                <Tag
                  aria-label={`质量${meta.label}，${Math.round(quality * 100)}%`}
                  color={meta.color}
                  title={`质量分 ${Math.round(quality * 100)}%`}
                >
                  {meta.label}
                </Tag>
              );
            },
          },
          {
            title: "审核",
            dataIndex: "reviewStatus",
            width: 110,
            render: (value) => (
              <Tag>{STATUS_LABELS[String(value)] ?? String(value)}</Tag>
            ),
          },
        ]}
        dataSource={result.items}
        loading={loading}
        locale={{ emptyText: <Empty description="没有符合条件的证据" /> }}
        onRow={(item) => ({
          onClick: () => setSelected(item),
          onKeyDown: (event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              setSelected(item);
            }
          },
          tabIndex: 0,
        })}
        pagination={{
          current: Math.floor(result.offset / result.limit) + 1,
          pageSize: result.limit,
          showSizeChanger: false,
          total: result.total,
          onChange: (page) => void search(page),
        }}
        rowClassName="evidence-browser-row"
        rowKey="id"
        scroll={{ x: 980 }}
      />
      <Drawer
        onClose={() => setSelected(null)}
        open={selected !== null}
        size="large"
        title="证据详情"
      >
        {selected ? (
          <div className="evidence-browser-detail">
            <p>{selected.fullText || selected.excerpt}</p>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="证据 ID">
                <code>{selected.id}</code>
              </Descriptions.Item>
              <Descriptions.Item label="来源">
                {sourceLabel(selected.source)}
              </Descriptions.Item>
              <Descriptions.Item label="声明类型">
                {CLAIM_LABELS[selected.claimType] ?? selected.claimType}
              </Descriptions.Item>
              <Descriptions.Item label="发布时间">
                {selected.publishedAt || "未登记"}
              </Descriptions.Item>
              <Descriptions.Item label="采集时间">
                {selected.collectedAt || "未登记"}
              </Descriptions.Item>
              <Descriptions.Item label="质量">
                {`${qualityMeta(selected.quality).label}（${Math.round(selected.quality * 100)}%）`}
              </Descriptions.Item>
              <Descriptions.Item label="审核状态">
                {STATUS_LABELS[selected.reviewStatus] ?? selected.reviewStatus}
              </Descriptions.Item>
            </Descriptions>
            {selected.sourceUrl ? (
              <Button href={selected.sourceUrl} target="_blank">
                打开原始来源
              </Button>
            ) : null}
          </div>
        ) : null}
      </Drawer>
    </section>
  );
}
