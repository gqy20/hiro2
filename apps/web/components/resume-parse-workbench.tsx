"use client";

// F-T3.4 简历解析确认：上传 PDF/DOCX/TXT -> 解析归一 -> 人工修正 -> 确认。
// 确认结果当前为会话内闭环（候选人持久化端点未提供），修正不落库。

import { useEffect, useState } from "react";
import { FileArrowUp, Trash } from "@phosphor-icons/react";
import { Button, Input, Tag, Upload, message } from "antd";

import { AppShell } from "@/components/app-shell";
import { apiFetch, isMockMode } from "@/lib/api/client";

type ParsedSkill = {
  mention: string;
  skill_id: string | null;
  proficiency: string;
  resolved_by: string;
  reason: string;
};

type ParseResponse = {
  rawText: string;
  profile: {
    name: string;
    education: string;
    experience_years: number | null;
    skills: ParsedSkill[];
    projects: { name: string; description: string }[];
  };
  stats: {
    totalSkills: number;
    resolved: number;
    byDict: number;
    byLlm: number;
    unresolved: number;
  };
};

type ResumeItem = { uid: string; file: File; status: "待解析" | "解析中" | "已完成" | "失败"; result?: ParseResponse; error?: string };

const RESOLVED_LABELS: Record<string, string> = {
  dict: "词典归一",
  llm: "LLM 归层",
  unmatched: "未命中",
};

const DEMO_RESULT: ParseResponse = {
  rawText:
    "张三，5 年后端经验……负责 RAG 检索服务（LangChain + Milvus），带领 3 人团队交付智能客服机器人……",
  profile: {
    name: "",
    education: "本科 计算机科学",
    experience_years: 5,
    skills: [
      { mention: "LangChain", skill_id: "cap_01", proficiency: "中级", resolved_by: "dict", reason: "" },
      { mention: "向量数据库", skill_id: null, proficiency: "中级", resolved_by: "llm", reason: "疑似 cap_06 RAG/知识库" },
      { mention: "团队管理", skill_id: "cap_25", proficiency: "高级", resolved_by: "dict", reason: "" },
    ],
    projects: [
      { name: "智能客服机器人", description: "RAG 检索 + 多轮对话，3 人团队" },
    ],
  },
  stats: { totalSkills: 3, resolved: 2, byDict: 2, byLlm: 0, unresolved: 1 },
};

export function ResumeParseWorkbench() {
  const [items, setItems] = useState<ResumeItem[]>([]);
  const [selectedUid, setSelectedUid] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [result, setResult] = useState<ParseResponse | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [skills, setSkills] = useState<ParsedSkill[]>([]);
  const selected = items.find((item) => item.uid === selectedUid) ?? null;
  const file = selected?.file ?? null;

  useEffect(() => {
    if (!file || !file.type.startsWith("text/")) return;
    file.text().then((text) => setPreview(text.slice(0, 1200))).catch(() => setPreview(""));
  }, [file]);
  const [preview, setPreview] = useState("");

  async function parse(target: ResumeItem) {
    setParsing(true);
    setItems((current) => current.map((item) => item.uid === target.uid ? { ...item, status: "解析中" } : item));
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
      setItems((current) => current.map((item) => item.uid === target.uid ? { ...item, status: "已完成", result: data } : item));
      if (target.uid === selectedUid) { setResult(data); setSkills(data.profile.skills); }
    } catch (err) {
      const error = err instanceof Error ? err.message : "解析失败，请稍后重试";
      setItems((current) => current.map((item) => item.uid === target.uid ? { ...item, status: "失败", error } : item));
      message.error(error);
    } finally {
      setParsing(false);
    }
  }

  async function parseAll() {
    for (const item of items.filter((entry) => entry.status === "待解析" || entry.status === "失败")) await parse(item);
  }

  function updateSkill(index: number, patch: Partial<ParsedSkill>) {
    setSkills((current) =>
      current.map((s, i) => (i === index ? { ...s, ...patch } : s)),
    );
  }

  return (
    <AppShell>
      <section aria-labelledby="resume-parse-title" className="resume-parse">
        <div className="page-heading">
          <div className="title-with-meta">
            <h1 id="resume-parse-title">简历解析确认</h1>
          <span className="page-meta">上传文件 → 解析归一 → 人工修正 → 确认</span>
          </div>
        </div>

        <Upload.Dragger
          accept=".pdf,.docx,.txt,.md"
          beforeUpload={(f) => {
            const item = { uid: `${f.name}-${f.size}-${f.lastModified}`, file: f, status: "待解析" as const };
            setItems((current) => current.some((entry) => entry.uid === item.uid) ? current : [...current, item]);
            setSelectedUid(item.uid);
            setResult(null);
            return false;
          }}
          multiple
          maxCount={10}
          showUploadList={false}
        >
          <p className="ant-upload-drag-icon"><FileArrowUp size={32} /></p>
          <p className="ant-upload-text">
            {file ? `${file.name} · ${formatBytes(file.size)}` : "点击或拖拽简历文件（支持多份）"}
          </p>
        </Upload.Dragger>

        <div className="resume-parse-actions">
          <Button
            disabled={items.length === 0 || parsing}
            loading={parsing}
            onClick={() => selected && parse(selected)}
            type="primary"
          >
            解析当前简历
          </Button>
          <Button disabled={items.length === 0 || parsing} onClick={parseAll}>解析全部 {items.length ? `(${items.length})` : ""}</Button>
        </div>

        {items.length > 0 ? <div className="resume-queue" aria-label="简历处理队列"><div className="resume-queue-heading"><strong>处理队列</strong><span>{`${items.filter((item) => item.status === "已完成").length} / ${items.length} 已完成`}</span></div>{items.map((item) => <button className={item.uid === selectedUid ? "resume-queue-item is-active" : "resume-queue-item"} key={item.uid} onClick={() => { setSelectedUid(item.uid); if (item.result) { setResult(item.result); setSkills(item.result.profile.skills); } }} type="button"><span><strong>{item.file.name}</strong><small>{formatBytes(item.file.size)}</small></span><em className={`resume-status resume-status-${item.status}`}>{item.status}</em></button>)}</div> : null}

        {file && !result ? <section className="resume-preview" aria-label="简历预览"><div><strong>文件预览</strong><span>{file.type || "未知格式"}</span></div>{preview ? <pre>{preview}{preview.length >= 1200 ? "…" : ""}</pre> : <p>该格式将在解析后显示结构化内容，当前文件已加入处理队列。</p>}</section> : null}

        {result ? (
          <div className="resume-parse-result">
            <div className="training-tags">
              <Tag color="blue">{`技能 ${result.stats.totalSkills}`}</Tag>
              <Tag color="green">{`归一 ${result.stats.resolved}`}</Tag>
              <Tag>{`词典 ${result.stats.byDict}`}</Tag>
              <Tag>{`LLM ${result.stats.byLlm}`}</Tag>
              <Tag color="orange">{`未命中 ${result.stats.unresolved}`}</Tag>
              {result.profile.education ? <Tag>{result.profile.education}</Tag> : null}
              {result.profile.experience_years !== null ? (
                <Tag>{`${result.profile.experience_years} 年经验`}</Tag>
              ) : null}
            </div>

            <h3>技能归一结果（可修正）</h3>
            <ul className="resume-skill-list">
              {skills.map((s, i) => (
                <li key={`${s.mention}-${i}`}>
                  <span className="task-name">{s.mention}</span>
                  <Tag>{RESOLVED_LABELS[s.resolved_by] ?? s.resolved_by}</Tag>
                  <Input
                    onChange={(e) => updateSkill(i, { skill_id: e.target.value })}
                    placeholder="能力 ID（如 cap_01）"
                    size="small"
                    style={{ width: 140 }}
                    value={s.skill_id ?? ""}
                  />
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

            {result.profile.projects.length > 0 ? (
              <>
                <h3>项目</h3>
                <ul className="resume-skill-list">
                  {result.profile.projects.map((p) => (
                    <li key={p.name}>
                      <span className="task-name">{p.name}</span>
                      <p className="publish-hint">{p.description}</p>
                    </li>
                  ))}
                </ul>
              </>
            ) : null}

            <h3>原文片段</h3>
            <details className="resume-raw">
              <summary>展开解析原文（截断 2000 字）</summary>
              <pre>{result.rawText}</pre>
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
            </div>
          </div>
        ) : null}
      </section>
    </AppShell>
  );
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}
