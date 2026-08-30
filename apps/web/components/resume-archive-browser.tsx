"use client";

import { useMemo, useState } from "react";
import {
  Alert,
  Button,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Select,
  Table,
  Tabs,
  Tag,
} from "antd";

import { apiFetch, getApiBaseUrl } from "@/lib/api/client";
import type {
  ResumeArchiveDetail,
  ResumeArchiveItem,
} from "@/lib/resume-archive";

const SAMPLE_LABELS: Record<ResumeArchiveItem["sample_type"], string> = {
  synthetic: "合成测试",
  anonymized: "脱敏样本",
  uploaded: "用户上传",
  controlled: "受控导入",
};

const SAMPLE_COLORS: Record<ResumeArchiveItem["sample_type"], string> = {
  synthetic: "gold",
  anonymized: "blue",
  uploaded: "green",
  controlled: "default",
};

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / 1024 / 1024).toFixed(1)} MB`;
}

function parseState(item: ResumeArchiveItem): { label: string; color: string } {
  if (item.stats) {
    if (item.parse_mode === "deterministic_fallback") {
      return { label: "词典解析", color: "blue" };
    }
    if (item.parse_mode === "shared_case_profile") {
      return { label: "共享画像", color: "cyan" };
    }
    return {
      label: item.parse_mode === "llm" ? "模型解析" : "已解析",
      color: "green",
    };
  }
  if (item.parse_error) return { label: "解析失败", color: "red" };
  return { label: "待解析", color: "default" };
}

function mockDetail(item: ResumeArchiveItem): ResumeArchiveDetail {
  return {
    resumeId: item.resume_id,
    filename: item.filename,
    size: item.size,
    suffix: item.suffix,
    uploadedAt: item.uploaded_at,
    source: item.source,
    sampleType: item.sample_type,
    parseMode: item.parse_mode,
    parseError: item.parse_error,
    rawText: "合成测试简历，用于验证简历解析、技能归一和人岗诊断流程。",
    stats: item.stats,
    profile: {
      location: "深圳",
      experience_years: 5,
      education: "本科 计算机科学",
      skills: [
        {
          mention: "AI Agent",
          skill_id: "cap_04",
          proficiency: "中级",
          resolved_by: "dict",
          reason: "",
        },
      ],
      projects: [{ name: "智能体工作流", description: "多步骤工具调用与评测" }],
    },
  };
}

export function ResumeArchiveBrowser({
  archive,
  mockMode,
}: {
  archive: ResumeArchiveItem[];
  mockMode: boolean;
}) {
  const [query, setQuery] = useState("");
  const [sampleType, setSampleType] = useState("");
  const [format, setFormat] = useState("");
  const [parseStatus, setParseStatus] = useState("");
  const [selected, setSelected] = useState<ResumeArchiveDetail | null>(null);
  const [loading, setLoading] = useState(false);

  const rows = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("zh-CN");
    return archive.filter((item) => {
      if (needle && !item.filename.toLocaleLowerCase("zh-CN").includes(needle))
        return false;
      if (sampleType && item.sample_type !== sampleType) return false;
      if (format && item.suffix.toLowerCase() !== format) return false;
      if (parseStatus === "parsed" && !item.stats) return false;
      if (parseStatus === "failed" && (!item.parse_error || item.stats))
        return false;
      if (parseStatus === "pending" && (item.stats || item.parse_error))
        return false;
      return true;
    });
  }, [archive, format, parseStatus, query, sampleType]);

  async function openResume(item: ResumeArchiveItem) {
    setLoading(true);
    try {
      setSelected(
        mockMode
          ? mockDetail(item)
          : await apiFetch<ResumeArchiveDetail>(
              `/candidates/resumes/${encodeURIComponent(item.resume_id)}`,
            ),
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="resume-records">
      <div className="resume-records-toolbar">
        <div>
          <strong>{`${rows.length} / ${archive.length} 份简历`}</strong>
          <span>{`已解析 ${archive.filter((item) => item.stats).length}`}</span>
          <Button href="/resumes" size="small">
            上传与解析
          </Button>
        </div>
        <Input
          allowClear
          aria-label="搜索简历文件"
          onChange={(event) => setQuery(event.target.value)}
          placeholder="搜索文件名"
          value={query}
        />
        <Select
          aria-label="筛选样本性质"
          onChange={setSampleType}
          options={[
            { label: "全部样本", value: "" },
            ...Object.entries(SAMPLE_LABELS).map(([value, label]) => ({
              value,
              label,
            })),
          ]}
          value={sampleType}
        />
        <Select
          aria-label="筛选文件格式"
          onChange={setFormat}
          options={[
            { label: "全部格式", value: "" },
            { label: "PDF", value: ".pdf" },
            { label: "DOCX", value: ".docx" },
          ]}
          value={format}
        />
        <Select
          aria-label="筛选解析状态"
          onChange={setParseStatus}
          options={[
            { label: "全部状态", value: "" },
            { label: "已解析", value: "parsed" },
            { label: "解析失败", value: "failed" },
            { label: "待解析", value: "pending" },
          ]}
          value={parseStatus}
        />
      </div>
      <Table<ResumeArchiveItem>
        columns={[
          {
            title: "简历文件",
            dataIndex: "filename",
            render: (_, item) => (
              <span className="resume-record-name">
                <strong>{item.filename}</strong>
                <small>{formatBytes(item.size)}</small>
              </span>
            ),
          },
          {
            title: "样本性质",
            dataIndex: "sample_type",
            width: 120,
            render: (value: ResumeArchiveItem["sample_type"]) => (
              <Tag color={SAMPLE_COLORS[value]}>{SAMPLE_LABELS[value]}</Tag>
            ),
          },
          {
            title: "格式",
            dataIndex: "suffix",
            width: 90,
            render: (value) => String(value).slice(1).toUpperCase(),
          },
          {
            title: "解析状态",
            width: 110,
            render: (_, item) => {
              const state = parseState(item);
              return <Tag color={state.color}>{state.label}</Tag>;
            },
          },
          {
            title: "技能",
            width: 130,
            render: (_, item) =>
              item.stats
                ? `${item.stats.resolved} / ${item.stats.totalSkills}`
                : "—",
          },
          {
            title: "入档时间",
            dataIndex: "uploaded_at",
            width: 130,
            render: (value) => String(value).slice(0, 10),
          },
        ]}
        dataSource={rows}
        loading={loading}
        locale={{ emptyText: <Empty description="没有符合条件的简历" /> }}
        onRow={(item) => ({
          onClick: () => void openResume(item),
          onKeyDown: (event) => {
            if (event.key === "Enter" || event.key === " ") {
              event.preventDefault();
              void openResume(item);
            }
          },
          tabIndex: 0,
        })}
        pagination={{ pageSize: 50, showSizeChanger: false }}
        rowClassName="resume-record-row"
        rowKey="resume_id"
        scroll={{ x: 900 }}
        size="middle"
      />

      <Drawer
        onClose={() => setSelected(null)}
        open={selected !== null}
        size="large"
        title={selected?.filename ?? "简历详情"}
      >
        {selected ? (
          <div className="resume-record-detail">
            {selected.sampleType === "synthetic" ? (
              <Alert
                title="合成测试简历"
                description="仅用于比赛演示、解析评测和流程验证，不代表真实候选人。"
                showIcon
              />
            ) : null}
            <Tabs
              items={[
                {
                  key: "profile",
                  label: "结构化画像",
                  children: <ResumeProfile detail={selected} />,
                },
                {
                  key: "document",
                  label: "文档预览",
                  children: mockMode ? (
                    <p>{selected.rawText}</p>
                  ) : (
                    <iframe
                      className="resume-record-preview"
                      src={`${getApiBaseUrl()}/candidates/resumes/${encodeURIComponent(selected.resumeId)}/preview`}
                      title="简历文档预览"
                    />
                  ),
                },
                {
                  key: "processing",
                  label: "处理信息",
                  children: (
                    <Descriptions bordered column={1} size="small">
                      <Descriptions.Item label="简历 ID">
                        <code>{selected.resumeId}</code>
                      </Descriptions.Item>
                      <Descriptions.Item label="来源">
                        {selected.source}
                      </Descriptions.Item>
                      <Descriptions.Item label="样本性质">
                        {SAMPLE_LABELS[selected.sampleType]}
                      </Descriptions.Item>
                      <Descriptions.Item label="解析方式">
                        {selected.parseMode === "deterministic_fallback"
                          ? "技能词典基础解析"
                          : selected.parseMode === "shared_case_profile"
                            ? "同案例共享结构化画像"
                            : selected.parseMode === "llm"
                              ? "模型结构化解析"
                              : "未记录"}
                      </Descriptions.Item>
                      {selected.parseError ? (
                        <Descriptions.Item label="解析错误">
                          {selected.parseError}
                        </Descriptions.Item>
                      ) : null}
                      <Descriptions.Item label="入档时间">
                        {selected.uploadedAt}
                      </Descriptions.Item>
                      <Descriptions.Item label="文件大小">
                        {formatBytes(selected.size)}
                      </Descriptions.Item>
                    </Descriptions>
                  ),
                },
              ]}
            />
          </div>
        ) : null}
      </Drawer>
    </div>
  );
}

function ResumeProfile({ detail }: { detail: ResumeArchiveDetail }) {
  const profile = detail.profile;
  return (
    <div className="resume-record-profile">
      <Descriptions bordered column={1} size="small">
        <Descriptions.Item label="职业摘要">
          {[
            profile.location,
            profile.experience_years == null
              ? ""
              : `${profile.experience_years} 年经验`,
            profile.education,
          ]
            .filter(Boolean)
            .join(" · ") || "尚未解析"}
        </Descriptions.Item>
        <Descriptions.Item label="技能">
          {profile.skills?.length
            ? profile.skills.map((skill) => skill.mention).join("、")
            : "尚未解析"}
        </Descriptions.Item>
        <Descriptions.Item label="项目">
          {profile.projects?.length
            ? profile.projects.map((project) => project.name).join("、")
            : "尚未解析"}
        </Descriptions.Item>
      </Descriptions>
      {profile.work_experiences?.length ? (
        <section>
          <h3>工作经历</h3>
          {profile.work_experiences.map((item, index) => (
            <article key={`${item.company}-${index}`}>
              <strong>{item.title}</strong>
              <span>{item.company}</span>
              <p>{item.summary}</p>
            </article>
          ))}
        </section>
      ) : null}
    </div>
  );
}
