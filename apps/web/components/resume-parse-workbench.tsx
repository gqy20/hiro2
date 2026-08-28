"use client";

// F-T3.4 简历解析确认：上传 PDF/DOCX/TXT -> 解析归一 -> 人工修正 -> 确认。
// 解析成功自动入档（objects 落盘 + JSONL），档案网格跨会话可见；
// imported 档案仅登记未解析，确认闭环仍为会话内。

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowRight, FileArrowUp, Trash } from "@phosphor-icons/react";
import { Button, Tag, Upload, message } from "antd";

import { AppShell } from "@/components/app-shell";
import { apiFetch, getApiBaseUrl, isMockMode } from "@/lib/api/client";

type ParsedSkill = {
  mention: string;
  skill_id: string | null;
  proficiency: string;
  resolved_by: string;
  reason: string;
};

type ParseStats = {
  totalSkills: number;
  resolved: number;
  byDict: number;
  byLlm: number;
  unresolved: number;
};

type ParseResponse = {
  rawText: string;
  profile: {
    education: string;
    experience_years: number | null;
    location?: string;
    work_experiences?: Array<{
      company: string;
      title: string;
      start_date: string;
      end_date: string;
      summary: string;
      achievements: string[];
      skill_mentions: string[];
    }>;
    education_history?: Array<{
      school: string;
      major: string;
      degree: string;
      start_date: string;
      end_date: string;
    }>;
    certificates?: Array<{ name: string; issuer: string; issued_date: string }>;
    portfolio_urls?: string[];
    languages?: string[];
    skills: ParsedSkill[];
    projects: { name: string; description: string }[];
  };
  stats: ParseStats;
  resumeId?: string;
};

// 档案列表项（后端 list_archive 为 snake_case 轻字段）
export type ResumeArchiveItem = {
  resume_id: string;
  filename: string;
  size: number;
  suffix: string;
  uploaded_at: string;
  source: string;
  stats: ParseStats | null;
};

type ResumeItem = {
  uid: string;
  file: File;
  status: "待解析" | "解析中" | "已完成" | "失败";
  result?: ParseResponse;
  error?: string;
};

const RESOLVED_LABELS: Record<string, string> = {
  dict: "已识别",
  llm: "已识别",
  unmatched: "待确认",
};

const DEMO_RESULT: ParseResponse = {
  rawText:
    "张三，5 年后端经验……负责 RAG 检索服务（LangChain + Milvus），带领 3 人团队交付智能客服机器人……",
  profile: {
    education: "本科 计算机科学",
    experience_years: 5,
    location: "深圳",
    work_experiences: [
      {
        company: "某科技公司",
        title: "后端工程师",
        start_date: "2021-07",
        end_date: "至今",
        summary: "负责智能客服与检索服务的后端架构。",
        achievements: ["带领 3 人团队交付智能客服机器人"],
        skill_mentions: ["LangChain", "Milvus"],
      },
    ],
    education_history: [
      {
        school: "某大学",
        major: "计算机科学",
        degree: "本科",
        start_date: "2016",
        end_date: "2020",
      },
    ],
    certificates: [],
    portfolio_urls: [],
    languages: [],
    skills: [
      {
        mention: "LangChain",
        skill_id: "cap_01",
        proficiency: "中级",
        resolved_by: "dict",
        reason: "",
      },
      {
        mention: "向量数据库",
        skill_id: null,
        proficiency: "中级",
        resolved_by: "llm",
        reason: "疑似 cap_06 RAG/知识库",
      },
      {
        mention: "团队管理",
        skill_id: "cap_25",
        proficiency: "高级",
        resolved_by: "dict",
        reason: "",
      },
    ],
    projects: [
      { name: "智能客服机器人", description: "RAG 检索 + 多轮对话，3 人团队" },
    ],
  },
  stats: { totalSkills: 3, resolved: 2, byDict: 2, byLlm: 0, unresolved: 1 },
};

export function ResumeParseWorkbench({
  initialArchive,
}: {
  initialArchive: ResumeArchiveItem[];
}) {
  const [items, setItems] = useState<ResumeItem[]>([]);
  const [selectedUid, setSelectedUid] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [result, setResult] = useState<ParseResponse | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [skills, setSkills] = useState<ParsedSkill[]>([]);
  const [preview, setPreview] = useState("");
  const [archive, setArchive] = useState<ResumeArchiveItem[]>(initialArchive);
  const [activeArchiveId, setActiveArchiveId] = useState<string | null>(null);
  const [previewMode, setPreviewMode] = useState<"document" | "profile">(
    "profile",
  );
  const [previewError, setPreviewError] = useState(false);
  const selected = items.find((item) => item.uid === selectedUid) ?? null;
  const file = selected?.file ?? null;
  const reviewArchive = archive.filter((entry) =>
    [".pdf", ".docx"].includes(entry.suffix || getSuffix(entry.filename)),
  );

  useEffect(() => {
    if (!file || !file.type.startsWith("text/")) return;
    file
      .text()
      .then((text) => setPreview(redactResumeText(text.slice(0, 1200))))
      .catch(() => setPreview(""));
  }, [file]);

  async function parse(target: ResumeItem) {
    setParsing(true);
    setItems((current) =>
      current.map((item) =>
        item.uid === target.uid ? { ...item, status: "解析中" } : item,
      ),
    );
    setConfirmed(false);
    try {
      let data: ParseResponse;
      if (isMockMode()) {
        await new Promise((resolve) => setTimeout(resolve, 1200));
        data = DEMO_RESULT;
      } else {
        const form = new FormData();
        form.append("file", target.file);
        data = await apiFetch<ParseResponse>("/candidates/resumes", {
          method: "POST",
          body: form,
          timeoutMs: 90_000, // LLM 抽取 + 双层归一，放宽超时
        });
      }
      setItems((current) =>
        current.map((item) =>
          item.uid === target.uid
            ? { ...item, status: "已完成", result: data }
            : item,
        ),
      );
      // 入档成功：新档案置顶到档案网格
      if (data.resumeId) {
        setActiveArchiveId(data.resumeId);
        setArchive((current) => [
          {
            resume_id: data.resumeId as string,
            filename: target.file.name,
            size: target.file.size,
            suffix: "",
            uploaded_at: new Date().toISOString().slice(0, 19),
            source: "upload",
            stats: data.stats,
          },
          ...current,
        ]);
      }
      if (target.uid === selectedUid) {
        setResult(data);
        setSkills(data.profile.skills);
        setPreviewMode("profile");
        setPreviewError(false);
      }
    } catch (err) {
      const error = err instanceof Error ? err.message : "解析失败，请稍后重试";
      setItems((current) =>
        current.map((item) =>
          item.uid === target.uid ? { ...item, status: "失败", error } : item,
        ),
      );
      message.error(error);
    } finally {
      setParsing(false);
    }
  }

  async function parseAll() {
    for (const item of items.filter(
      (entry) => entry.status === "待解析" || entry.status === "失败",
    ))
      await parse(item);
  }

  // 打开档案：已解析的拉详情展示，imported 未解析给明确提示
  async function openArchive(entry: ResumeArchiveItem) {
    setSelectedUid(null);
    setActiveArchiveId(entry.resume_id);
    setPreviewMode("profile");
    setPreviewError(false);
    setConfirmed(false);
    if (!entry.stats) {
      setResult(null);
      message.info("导入档案尚未解析：上传后解析可生成画像");
      return;
    }
    if (isMockMode()) {
      setResult(DEMO_RESULT);
      setSkills(DEMO_RESULT.profile.skills);
      return;
    }
    try {
      const d = await apiFetch<{
        resumeId: string;
        rawText: string;
        profile: ParseResponse["profile"];
        stats: ParseStats;
      }>(`/candidates/resumes/${encodeURIComponent(entry.resume_id)}`);
      setResult({
        rawText: d.rawText,
        profile: d.profile,
        stats: d.stats,
        resumeId: d.resumeId,
      });
      setSkills(d.profile.skills ?? []);
    } catch (err) {
      message.error(err instanceof Error ? err.message : "档案读取失败");
    }
  }

  return (
    <AppShell>
      <section
        aria-labelledby="resume-parse-title"
        className={`resume-parse${activeArchiveId || result ? " has-selection" : ""}`}
      >
        <div className="page-heading">
          <div className="title-with-meta">
            <h1 id="resume-parse-title">简历解析确认</h1>
            <span className="page-meta">
              上传文件 → 解析归一 → 人工修正 → 确认
            </span>
          </div>
        </div>

        <Upload.Dragger
          accept=".pdf,.docx,.txt,.md"
          beforeUpload={(f) => {
            const item = {
              uid: `${f.name}-${f.size}-${f.lastModified}`,
              file: f,
              status: "待解析" as const,
            };
            setItems((current) =>
              current.some((entry) => entry.uid === item.uid)
                ? current
                : [...current, item],
            );
            setSelectedUid(item.uid);
            setActiveArchiveId(null);
            setPreviewMode("profile");
            setPreviewError(false);
            setResult(null);
            return false;
          }}
          multiple
          maxCount={10}
          showUploadList={false}
        >
          <p className="ant-upload-drag-icon">
            <FileArrowUp size={32} />
          </p>
          <p className="ant-upload-text">
            {file
              ? `${file.name} · ${formatBytes(file.size)}`
              : "点击或拖拽简历文件（支持多份）"}
          </p>
        </Upload.Dragger>

        <section className="resume-archive" aria-label="简历档案">
          <div className="resume-queue-heading">
            <strong>{`简历档案（${reviewArchive.length}）`}</strong>
            <span>{`已解析 ${reviewArchive.filter((a) => a.stats).length} · 待解析 ${reviewArchive.filter((a) => !a.stats).length}`}</span>
          </div>
          {reviewArchive.length > 0 ? (
            <div className="resume-archive-grid">
              {reviewArchive.map((entry) => (
                <button
                  className={
                    entry.resume_id === activeArchiveId
                      ? "resume-archive-card is-active"
                      : "resume-archive-card"
                  }
                  key={entry.resume_id}
                  onClick={() => openArchive(entry)}
                  type="button"
                >
                  <strong title={entry.filename}>{entry.filename}</strong>
                  <small>{entry.uploaded_at.slice(0, 10)}</small>
                  {entry.stats ? (
                    <em className="resume-status resume-status-已完成">
                      {`${entry.stats.totalSkills} 技能 · 归一 ${entry.stats.resolved}`}
                    </em>
                  ) : (
                    <em className="resume-status resume-status-待解析">
                      未解析
                    </em>
                  )}
                  <Tag
                    className={`resume-format resume-format-${(entry.suffix || getSuffix(entry.filename)).slice(1)}`}
                  >
                    {(entry.suffix || getSuffix(entry.filename))
                      .slice(1)
                      .toUpperCase()}
                  </Tag>
                </button>
              ))}
            </div>
          ) : (
            <p className="publish-hint">
              档案为空：上传或导入的简历会出现在这里。
            </p>
          )}
        </section>

        <div className="resume-parse-actions">
          <Button
            disabled={items.length === 0 || parsing}
            loading={parsing}
            onClick={() => selected && parse(selected)}
            type="primary"
          >
            解析当前简历
          </Button>
          <Button disabled={items.length === 0 || parsing} onClick={parseAll}>
            解析全部 {items.length ? `(${items.length})` : ""}
          </Button>
        </div>

        {items.length > 0 ? (
          <div className="resume-queue" aria-label="简历处理队列">
            <div className="resume-queue-heading">
              <strong>处理队列</strong>
              <span>{`${items.filter((item) => item.status === "已完成").length} / ${items.length} 已完成`}</span>
            </div>
            {items.map((item) => (
              <button
                className={
                  item.uid === selectedUid
                    ? "resume-queue-item is-active"
                    : "resume-queue-item"
                }
                key={item.uid}
                onClick={() => {
                  setSelectedUid(item.uid);
                  if (item.result) {
                    setResult(item.result);
                    setSkills(item.result.profile.skills);
                  }
                }}
                type="button"
              >
                <span>
                  <strong>{item.file.name}</strong>
                  <small>{formatBytes(item.file.size)}</small>
                </span>
                <em className={`resume-status resume-status-${item.status}`}>
                  {item.status}
                </em>
              </button>
            ))}
          </div>
        ) : null}

        {file && !result ? (
          <section className="resume-preview" aria-label="简历预览">
            <div>
              <strong>文件预览</strong>
              <span>{file.type || "未知格式"}</span>
            </div>
            {preview ? (
              <pre>
                {preview}
                {preview.length >= 1200 ? "…" : ""}
              </pre>
            ) : (
              <p>该格式将在解析后显示结构化内容，当前文件已加入处理队列。</p>
            )}
          </section>
        ) : null}

        {activeArchiveId || result ? (
          <div className="resume-selection-header">
            <div>
              <strong>当前简历</strong>
              <span>
                {activeArchiveId
                  ? archive.find((entry) => entry.resume_id === activeArchiveId)
                      ?.filename
                  : file?.name}
              </span>
            </div>
            <span>{result ? "已解析" : "待解析"}</span>
          </div>
        ) : null}

        {activeArchiveId || result ? (
          <div
            className="resume-document-tabs"
            role="tablist"
            aria-label="简历查看方式"
          >
            <button
              className={previewMode === "document" ? "is-active" : ""}
              onClick={() => setPreviewMode("document")}
              role="tab"
              aria-selected={previewMode === "document"}
              type="button"
            >
              文档预览
            </button>
            <button
              className={previewMode === "profile" ? "is-active" : ""}
              onClick={() => setPreviewMode("profile")}
              role="tab"
              aria-selected={previewMode === "profile"}
              type="button"
            >
              结构化档案
            </button>
          </div>
        ) : null}

        {previewMode === "document" && activeArchiveId ? (
          <section
            className="resume-document-preview"
            aria-label="原始文档预览"
          >
            {previewError ? (
              <div className="resume-document-preview-error">
                <strong>文档预览暂时不可用</strong>
                <span>可以继续查看结构化档案，或稍后重试。</span>
                <button onClick={() => setPreviewError(false)} type="button">
                  重新加载
                </button>
              </div>
            ) : (
              <iframe
                key={activeArchiveId}
                title="原始简历文档预览"
                onError={() => setPreviewError(true)}
                src={`${getApiBaseUrl()}/candidates/resumes/${encodeURIComponent(activeArchiveId)}/preview`}
              />
            )}
          </section>
        ) : null}

        {result && previewMode === "profile" ? (
          <div className="resume-parse-result">
            <section className="resume-profile-summary">
              <div>
                <h2>职业档案</h2>
                <p>
                  {[
                    result.profile.location,
                    result.profile.experience_years === null
                      ? ""
                      : `${result.profile.experience_years} 年经验`,
                    result.profile.education,
                  ]
                    .filter(Boolean)
                    .join(" · ") || "请确认职业信息"}
                </p>
              </div>
              <div className="training-tags">
                <Tag color="blue">{`技能 ${result.stats.totalSkills}`}</Tag>
                <Tag color="green">{`已归一 ${result.stats.resolved}`}</Tag>
                {result.stats.unresolved ? (
                  <Tag color="orange">{`${result.stats.unresolved} 项待确认`}</Tag>
                ) : null}
              </div>
            </section>

            {result.profile.work_experiences?.length ? (
              <section className="resume-structured-section">
                <h3>工作经历</h3>
                {result.profile.work_experiences.map((work, index) => (
                  <article
                    className="resume-experience"
                    key={`${work.company}-${work.title}-${index}`}
                  >
                    <div>
                      <strong>{work.title}</strong>
                      <span>{work.company}</span>
                    </div>
                    <small>
                      {[work.start_date, work.end_date]
                        .filter(Boolean)
                        .join(" - ")}
                    </small>
                    {work.summary ? <p>{work.summary}</p> : null}
                    {work.achievements?.length ? (
                      <ul>
                        {work.achievements.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : null}
                  </article>
                ))}
              </section>
            ) : null}

            {result.profile.projects.length > 0 ? (
              <section className="resume-structured-section">
                <h3>项目与能力证明</h3>
                <div className="resume-project-grid">
                  {result.profile.projects.map((p) => (
                    <article key={p.name}>
                      <strong>{p.name}</strong>
                      <p>{p.description}</p>
                    </article>
                  ))}
                </div>
              </section>
            ) : null}

            <section className="resume-structured-section">
              <h3>技能与匹配</h3>
              <ul className="resume-skill-list">
                {skills.map((s, i) => (
                  <li key={`${s.mention}-${i}`}>
                    <span className="task-name">{s.mention}</span>
                    <Tag color={s.skill_id ? "green" : "orange"}>
                      {RESOLVED_LABELS[s.resolved_by] ?? "待确认"}
                    </Tag>
                    <span className="resume-skill-level">{s.proficiency}</span>
                    <Button
                      icon={<Trash aria-hidden size={14} />}
                      onClick={() =>
                        setSkills((cur) => cur.filter((_, j) => j !== i))
                      }
                      size="small"
                      type="text"
                    />
                    {s.reason ? (
                      <p className="publish-hint">{s.reason}</p>
                    ) : null}
                  </li>
                ))}
              </ul>
            </section>

            {result.profile.education_history?.length ||
            result.profile.certificates?.length ||
            result.profile.languages?.length ? (
              <section className="resume-structured-section resume-background">
                <h3>教育与补充信息</h3>
                <div>
                  {result.profile.education_history?.map((edu, index) => (
                    <p key={`${edu.school}-${index}`}>
                      <strong>{edu.school}</strong>
                      {` · ${[edu.major, edu.degree, [edu.start_date, edu.end_date].filter(Boolean).join(" - ")].filter(Boolean).join(" · ")}`}
                    </p>
                  ))}
                  {result.profile.certificates?.map((certificate) => (
                    <p key={certificate.name}>
                      <strong>{certificate.name}</strong>
                      {certificate.issuer ? ` · ${certificate.issuer}` : ""}
                    </p>
                  ))}
                  {result.profile.languages?.length ? (
                    <p>{`语言：${result.profile.languages.join(" · ")}`}</p>
                  ) : null}
                </div>
              </section>
            ) : null}

            <h3>原始简历</h3>
            <details className="resume-raw">
              <summary>展开解析原文（截断 2000 字）</summary>
              <pre>{redactResumeText(result.rawText)}</pre>
            </details>

            <div className="resume-parse-actions">
              <Button
                disabled={confirmed}
                onClick={() => {
                  setConfirmed(true);
                  message.success(
                    "已确认（会话内）；候选人持久化端点接入后自动入库",
                  );
                }}
                type="primary"
              >
                {confirmed ? "已确认" : "确认画像"}
              </Button>
              {confirmed ? (
                <Link className="resume-parse-goto" href="/diagnosis">
                  前往诊断 <ArrowRight aria-hidden size={15} />
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}

function getSuffix(filename: string): string {
  const suffix = filename.slice(filename.lastIndexOf(".")).toLowerCase();
  return suffix === ".pdf" || suffix === ".docx" ? suffix : "";
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function redactResumeText(text: string): string {
  return text
    .replace(/[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}/gi, "***@***")
    .replace(/(?<!\*)1[3-9]\d{9}/g, "138****0000");
}
