"use client";

// 简历工作台：左侧草稿编辑 + PDF 预览，右侧确定性建议（随目标岗位切换）。
// 表单控件走 AntD 词汇（与诊断工作台一致），面板/卡片走 career 区 surface 语言。

import { FilePdf, Lightbulb, Plus } from "@phosphor-icons/react";
import { Button, Input, Select, Tag } from "antd";
import { useMemo, useState } from "react";
import Link from "next/link";

import { apiFetch, apiFetchBlob, isMockMode } from "@/lib/api/client";
import {
  buildMockAdvice,
  emptyDraft,
  type AdviceItemView,
  type AdviceView,
  type ResumeDraftInput,
} from "@/lib/resume-studio";

type JobOption = { version_id: string; title: string };

const SEVERITY_TAG: Record<string, { color: string; label: string }> = {
  high: { color: "red", label: "优先" },
  medium: { color: "orange", label: "建议" },
  low: { color: "green", label: "打磨" },
};
const KIND_LABEL: Record<string, string> = {
  coverage: "岗位对齐",
  specificity: "技能具体化",
  structure: "结构",
};

export function ResumeStudio({
  jobs,
  initialAdvice = null,
  initialDraft,
  initialJobId,
}: {
  jobs: JobOption[];
  initialAdvice?: AdviceView | null;
  initialDraft?: ResumeDraftInput;
  initialJobId?: string;
}) {
  const [draft, setDraft] = useState<ResumeDraftInput>(
    initialDraft ?? emptyDraft(),
  );
  const [jobId, setJobId] = useState<string>(
    initialJobId ?? jobs[0]?.version_id ?? "",
  );
  const [advice, setAdvice] = useState<AdviceView | null>(initialAdvice);
  const [pdfUrl, setPdfUrl] = useState<string>("");
  const [busy, setBusy] = useState<"advice" | "render" | null>(null);
  const [error, setError] = useState("");

  const set = <K extends keyof ResumeDraftInput>(
    key: K,
    value: ResumeDraftInput[K],
  ) => setDraft((d) => ({ ...d, [key]: value }));

  const jobTitle = useMemo(
    () => jobs.find((j) => j.version_id === jobId)?.title ?? jobId,
    [jobs, jobId],
  );

  async function loadAdvice() {
    setBusy("advice");
    setError("");
    try {
      if (isMockMode()) {
        setAdvice(buildMockAdvice(jobTitle));
      } else {
        setAdvice(
          await apiFetch<AdviceView>(
            `/career/resume/advice?job_version_id=${encodeURIComponent(jobId)}`,
            { method: "POST", body: draft, timeoutMs: 20000 },
          ),
        );
      }
    } catch (e) {
      setError(`建议获取失败：${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  async function renderPdf() {
    setBusy("render");
    setError("");
    try {
      const blob = await apiFetchBlob("/career/resume/render", {
        method: "POST",
        body: draft,
        timeoutMs: 30000,
      });
      setPdfUrl((old) => {
        if (old) URL.revokeObjectURL(old);
        return URL.createObjectURL(blob);
      });
    } catch (e) {
      setError(`PDF 生成失败：${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setBusy(null);
    }
  }

  function updateExperience(
    i: number,
    patch: Partial<ResumeDraftInput["experiences"][number]>,
  ) {
    set(
      "experiences",
      draft.experiences.map((x, j) => (j === i ? { ...x, ...patch } : x)),
    );
  }
  function updateProject(
    i: number,
    patch: Partial<ResumeDraftInput["projects"][number]>,
  ) {
    set(
      "projects",
      draft.projects.map((x, j) => (j === i ? { ...x, ...patch } : x)),
    );
  }

  return (
    <div className="resume-studio-page">
      <header className="page-heading">
        <div>
          <h1 className="sr-only">简历工作台</h1>
          <p>画像已自动带入草稿；补充经历后检查岗位覆盖，并生成投递 PDF。</p>
        </div>
      </header>
      <div className="resume-studio">
        <section className="resume-panel" aria-label="简历草稿编辑">
          <div className="resume-draft-heading">
            <div>
              <h2>投递简历</h2>
              <p>{`已从我的画像带入 ${draft.skills.length} 项技能、${draft.projects.length} 项能力证明`}</p>
            </div>
            <Link href="/profile">更新画像</Link>
          </div>
          <div className="resume-grid-2">
            <label className="resume-field">
              <span>姓名</span>
              <Input
                value={draft.name}
                onChange={(e) => set("name", e.target.value)}
                placeholder="张三"
              />
            </label>
            <label className="resume-field">
              <span>求职意向</span>
              <Input
                value={draft.title}
                onChange={(e) => set("title", e.target.value)}
                placeholder="如：AI 应用工程师"
              />
            </label>
          </div>
          <label className="resume-field">
            <span>联系方式</span>
            <Input
              value={draft.contact}
              onChange={(e) => set("contact", e.target.value)}
              placeholder="电话 ｜ 邮箱 ｜ 城市"
            />
          </label>
          <label className="resume-field">
            <span>个人概述</span>
            <Input.TextArea
              rows={3}
              value={draft.summary}
              onChange={(e) => set("summary", e.target.value)}
              placeholder="方向 + 年限 + 最相关的一项成果"
            />
          </label>
          <div className="resume-field">
            <span>专业技能（来自我的画像）</span>
            <div className="resume-skill-preview">
              {draft.skills.slice(0, 6).map((skill) => (
                <Tag key={skill}>{skill}</Tag>
              ))}
              {draft.skills.length > 6 ? (
                <span>{`另有 ${draft.skills.length - 6} 项`}</span>
              ) : null}
              <Link href="/profile">管理技能</Link>
            </div>
          </div>

          <div className="resume-section-head">
            <h3>工作经历</h3>
            <Button
              type="text"
              size="small"
              icon={<Plus />}
              onClick={() =>
                set("experiences", [
                  ...draft.experiences,
                  { company: "", role: "", period: "", bullets: [""] },
                ])
              }
            >
              添加
            </Button>
          </div>
          {draft.experiences.map((exp, i) => (
            <fieldset className="resume-block" key={i}>
              <div className="resume-grid-3">
                <Input
                  value={exp.company}
                  onChange={(e) =>
                    updateExperience(i, { company: e.target.value })
                  }
                  placeholder="公司"
                />
                <Input
                  value={exp.role}
                  onChange={(e) =>
                    updateExperience(i, { role: e.target.value })
                  }
                  placeholder="职位"
                />
                <Input
                  value={exp.period}
                  onChange={(e) =>
                    updateExperience(i, { period: e.target.value })
                  }
                  placeholder="2022-2024"
                />
              </div>
              <Input.TextArea
                rows={3}
                value={exp.bullets.join("\n")}
                onChange={(e) =>
                  updateExperience(i, { bullets: e.target.value.split("\n") })
                }
                placeholder={
                  "每行一条：职责、动作与量化结果\n例：负责 RAG 问答系统，日活 10 万，检索准确率 +12%"
                }
              />
            </fieldset>
          ))}

          <div className="resume-section-head">
            <h3>项目经历</h3>
            <Button
              type="text"
              size="small"
              icon={<Plus />}
              onClick={() =>
                set("projects", [
                  ...draft.projects,
                  { name: "", desc: "", bullets: [""] },
                ])
              }
            >
              添加
            </Button>
          </div>
          {draft.projects.map((p, i) => (
            <fieldset className="resume-block" key={i}>
              <div className="resume-grid-2">
                <Input
                  value={p.name}
                  onChange={(e) => updateProject(i, { name: e.target.value })}
                  placeholder="项目名"
                />
                <Input
                  value={p.desc}
                  onChange={(e) => updateProject(i, { desc: e.target.value })}
                  placeholder="一句话说明"
                />
              </div>
              <Input.TextArea
                rows={2}
                value={p.bullets.join("\n")}
                onChange={(e) =>
                  updateProject(i, { bullets: e.target.value.split("\n") })
                }
                placeholder="每行一条"
              />
            </fieldset>
          ))}

          <div className="resume-section-head">
            <h3>教育背景</h3>
          </div>
          {draft.education.map((ed, i) => (
            <div className="resume-grid-4" key={i}>
              <Input
                value={ed.school}
                onChange={(e) =>
                  set(
                    "education",
                    draft.education.map((x, j) =>
                      j === i ? { ...x, school: e.target.value } : x,
                    ),
                  )
                }
                placeholder="学校"
              />
              <Input
                value={ed.major}
                onChange={(e) =>
                  set(
                    "education",
                    draft.education.map((x, j) =>
                      j === i ? { ...x, major: e.target.value } : x,
                    ),
                  )
                }
                placeholder="专业"
              />
              <Input
                value={ed.degree}
                onChange={(e) =>
                  set(
                    "education",
                    draft.education.map((x, j) =>
                      j === i ? { ...x, degree: e.target.value } : x,
                    ),
                  )
                }
                placeholder="学历"
              />
              <Input
                value={ed.period}
                onChange={(e) =>
                  set(
                    "education",
                    draft.education.map((x, j) =>
                      j === i ? { ...x, period: e.target.value } : x,
                    ),
                  )
                }
                placeholder="2018-2022"
              />
            </div>
          ))}

          <div className="resume-actions">
            <Button
              type="primary"
              icon={<FilePdf />}
              loading={busy === "render"}
              disabled={busy !== null}
              onClick={renderPdf}
            >
              生成 PDF
            </Button>
            {pdfUrl && (
              <a
                className="resume-download"
                href={pdfUrl}
                download="resume.pdf"
              >
                下载 PDF
              </a>
            )}
          </div>
          {error && (
            <p className="resume-error" role="alert">
              {error}
            </p>
          )}
          {pdfUrl && (
            <div className="resume-preview">
              <iframe src={pdfUrl} title="简历 PDF 预览" />
            </div>
          )}
        </section>

        <aside className="resume-panel" aria-label="AI 建议">
          <div className="resume-advice-head">
            <h2>投递建议</h2>
            <Button
              type="primary"
              ghost
              icon={<Lightbulb />}
              loading={busy === "advice"}
              disabled={busy !== null || !jobId}
              onClick={loadAdvice}
            >
              {advice ? "重新分析" : "分析岗位匹配"}
            </Button>
          </div>
          <label className="resume-field">
            <span>目标岗位（建议随岗位切换）</span>
            <Select
              value={jobId || undefined}
              onChange={(value) => {
                setJobId(value);
                setAdvice(null);
              }}
              options={jobs.map((j) => ({
                value: j.version_id,
                label: j.title,
              }))}
              style={{ width: "100%" }}
              placeholder="选择目标岗位"
            />
          </label>
          {advice && (
            <p className="resume-coverage">
              必备技能覆盖 <b>{advice.required_covered}</b>/
              {advice.required_total}
              <span className="resume-coverage-job">
                （{advice.job_title}）
              </span>
            </p>
          )}
          <div className="resume-advice-list">
            {advice?.advice.map((a: AdviceItemView, i) => (
              <article className="resume-advice-card" key={i}>
                <header>
                  <Tag variant="filled">{KIND_LABEL[a.kind] ?? a.kind}</Tag>
                  <b>{a.title}</b>
                  <Tag
                    color={SEVERITY_TAG[a.severity]?.color}
                    className="resume-sev"
                    variant="filled"
                  >
                    {SEVERITY_TAG[a.severity]?.label ?? a.severity}
                  </Tag>
                </header>
                <p>{a.detail}</p>
                <p className="resume-advice-suggestion">{a.suggestion}</p>
                {(a.evidence.jd_count || a.evidence.weight) && (
                  <footer>
                    证据：
                    {a.evidence.jd_count ? ` ${a.evidence.jd_count} 条 JD` : ""}
                    {a.evidence.weight
                      ? ` · 市场权重 ${a.evidence.weight}`
                      : ""}
                  </footer>
                )}
              </article>
            ))}
            {!advice && (
              <p className="resume-advice-empty">
                填写技能与经历后点击「获取建议」，系统按目标岗位的市场证据给出对齐建议。
              </p>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
