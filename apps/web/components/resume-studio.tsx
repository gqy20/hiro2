"use client";

// 简历工作台：左侧草稿编辑 + PDF 预览，右侧确定性建议（随目标岗位切换）。

import { useMemo, useState } from "react";

import { apiFetch, isMockMode } from "@/lib/api/client";
import {
  buildMockAdvice,
  emptyDraft,
  type AdviceView,
  type ResumeDraftInput,
} from "@/lib/resume-studio";

type JobOption = { version_id: string; title: string };

const SEVERITY_LABEL: Record<string, string> = {
  high: "高",
  medium: "中",
  low: "低",
};
const KIND_LABEL: Record<string, string> = {
  coverage: "岗位对齐",
  specificity: "技能具体化",
  structure: "结构",
};

export function ResumeStudio({ jobs }: { jobs: JobOption[] }) {
  const [draft, setDraft] = useState<ResumeDraftInput>(emptyDraft());
  const [jobId, setJobId] = useState<string>(jobs[0]?.version_id ?? "");
  const [advice, setAdvice] = useState<AdviceView | null>(null);
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
      const res = await apiFetch<Response>("/career/resume/render", {
        method: "POST",
        body: draft,
        timeoutMs: 30000,
      });
      const blob = await res.blob();
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

  return (
    <div className="resume-studio">
      <section className="resume-editor" aria-label="简历草稿编辑">
        <div className="resume-field-row">
          <label>
            姓名
            <input
              value={draft.name}
              onChange={(e) => set("name", e.target.value)}
            />
          </label>
          <label>
            求职意向
            <input
              value={draft.title}
              onChange={(e) => set("title", e.target.value)}
              placeholder="如：AI 应用工程师"
            />
          </label>
        </div>
        <label className="resume-field">
          联系方式
          <input
            value={draft.contact}
            onChange={(e) => set("contact", e.target.value)}
            placeholder="电话 ｜ 邮箱 ｜ 城市"
          />
        </label>
        <label className="resume-field">
          个人概述
          <textarea
            rows={3}
            value={draft.summary}
            onChange={(e) => set("summary", e.target.value)}
            placeholder="方向 + 年限 + 最相关的一项成果"
          />
        </label>
        <label className="resume-field">
          专业技能（顿号分隔）
          <input
            value={draft.skills.join("、")}
            onChange={(e) =>
              set(
                "skills",
                e.target.value
                  .split(/、|,/)
                  .map((s) => s.trim())
                  .filter(Boolean),
              )
            }
            placeholder="Python、LangChain、RAG"
          />
        </label>

        <h3>工作经历</h3>
        {draft.experiences.map((exp, i) => (
          <fieldset className="resume-block" key={i}>
            <div className="resume-field-row">
              <input
                value={exp.company}
                onChange={(e) =>
                  set(
                    "experiences",
                    draft.experiences.map((x, j) =>
                      j === i ? { ...x, company: e.target.value } : x,
                    ),
                  )
                }
                placeholder="公司"
              />
              <input
                value={exp.role}
                onChange={(e) =>
                  set(
                    "experiences",
                    draft.experiences.map((x, j) =>
                      j === i ? { ...x, role: e.target.value } : x,
                    ),
                  )
                }
                placeholder="职位"
              />
              <input
                value={exp.period}
                onChange={(e) =>
                  set(
                    "experiences",
                    draft.experiences.map((x, j) =>
                      j === i ? { ...x, period: e.target.value } : x,
                    ),
                  )
                }
                placeholder="起止时间"
              />
            </div>
            <textarea
              rows={3}
              value={exp.bullets.join("\n")}
              onChange={(e) =>
                set(
                  "experiences",
                  draft.experiences.map((x, j) =>
                    j === i ? { ...x, bullets: e.target.value.split("\n") } : x,
                  ),
                )
              }
              placeholder="每行一条：职责、动作与量化结果"
            />
          </fieldset>
        ))}
        <button
          type="button"
          className="resume-add"
          onClick={() =>
            set("experiences", [
              ...draft.experiences,
              { company: "", role: "", period: "", bullets: [""] },
            ])
          }
        >
          + 添加经历
        </button>

        <h3>项目经历</h3>
        {draft.projects.map((p, i) => (
          <fieldset className="resume-block" key={i}>
            <div className="resume-field-row">
              <input
                value={p.name}
                onChange={(e) =>
                  set(
                    "projects",
                    draft.projects.map((x, j) =>
                      j === i ? { ...x, name: e.target.value } : x,
                    ),
                  )
                }
                placeholder="项目名"
              />
              <input
                value={p.desc}
                onChange={(e) =>
                  set(
                    "projects",
                    draft.projects.map((x, j) =>
                      j === i ? { ...x, desc: e.target.value } : x,
                    ),
                  )
                }
                placeholder="一句话说明"
              />
            </div>
            <textarea
              rows={2}
              value={p.bullets.join("\n")}
              onChange={(e) =>
                set(
                  "projects",
                  draft.projects.map((x, j) =>
                    j === i ? { ...x, bullets: e.target.value.split("\n") } : x,
                  ),
                )
              }
              placeholder="每行一条"
            />
          </fieldset>
        ))}
        <button
          type="button"
          className="resume-add"
          onClick={() =>
            set("projects", [
              ...draft.projects,
              { name: "", desc: "", bullets: [""] },
            ])
          }
        >
          + 添加项目
        </button>

        <h3>教育背景</h3>
        {draft.education.map((ed, i) => (
          <div className="resume-field-row" key={i}>
            <input
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
            <input
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
            <input
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
            <input
              value={ed.period}
              onChange={(e) =>
                set(
                  "education",
                  draft.education.map((x, j) =>
                    j === i ? { ...x, period: e.target.value } : x,
                  ),
                )
              }
              placeholder="时间段"
            />
          </div>
        ))}

        <div className="resume-actions">
          <button type="button" onClick={renderPdf} disabled={busy !== null}>
            {busy === "render" ? "生成中…" : "生成 PDF 预览"}
          </button>
          {pdfUrl && (
            <a className="resume-download" href={pdfUrl} download="resume.pdf">
              下载 PDF
            </a>
          )}
        </div>
        {error && (
          <p className="resume-error" role="alert">
            {error}
          </p>
        )}
      </section>

      <aside className="resume-advice" aria-label="AI 建议">
        <div className="resume-advice-head">
          <label>
            目标岗位
            <select value={jobId} onChange={(e) => setJobId(e.target.value)}>
              {jobs.map((j) => (
                <option key={j.version_id} value={j.version_id}>
                  {j.title}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={loadAdvice}
            disabled={busy !== null || !jobId}
          >
            {busy === "advice" ? "分析中…" : "获取建议"}
          </button>
        </div>
        {advice && (
          <p className="resume-coverage">
            必备技能覆盖 {advice.required_covered}/{advice.required_total}（
            {advice.job_title}）
          </p>
        )}
        {advice?.advice.map((a, i) => (
          <article key={i} className={`resume-advice-card sev-${a.severity}`}>
            <header>
              <span className="resume-advice-kind">
                {KIND_LABEL[a.kind] ?? a.kind}
              </span>
              <b>{a.title}</b>
              <span className={`resume-sev sev-${a.severity}`}>
                {SEVERITY_LABEL[a.severity] ?? a.severity}
              </span>
            </header>
            <p>{a.detail}</p>
            <p className="resume-advice-suggestion">{a.suggestion}</p>
            {(a.evidence.jd_count || a.evidence.weight) && (
              <footer>
                证据：
                {a.evidence.jd_count ? `${a.evidence.jd_count} 条 JD` : ""}
                {a.evidence.weight ? ` · 市场权重 ${a.evidence.weight}` : ""}
              </footer>
            )}
          </article>
        ))}
        {pdfUrl && (
          <div className="resume-preview">
            <h3>PDF 预览</h3>
            <iframe src={pdfUrl} title="简历 PDF 预览" />
          </div>
        )}
      </aside>
    </div>
  );
}
