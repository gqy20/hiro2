"use client";

import { useState } from "react";
import {
  CheckCircle,
  PencilSimple,
  Plus,
  Trash,
} from "@phosphor-icons/react";
import { Button, Input, Select, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { EvidenceDrawer } from "@/components/evidence-drawer";
import { ConfidenceMeter, StatusMark } from "@/components/review-ui";
import { FixtureState, skillStatusToReview } from "@/components/workflow-ui";
import { SectionHeader } from "@/components/workflow-ui";
import type {
  DiagnosisFixture,
  ProjectEntry,
  SkillMatch,
  UserCorrection,
} from "@/lib/diagnosis";
import type { ChangeItem, JobUpdateContext } from "@/lib/job-update";

const SKILL_STATUSES: Array<SkillMatch["status"]> = ["ready", "partial", "missing"];

function makeCorrectionId(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

function makeProjectId(): string {
  return `proj-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
}

function nowDate(): string {
  return new Date().toISOString().slice(0, 10);
}

export function DiagnosisWorkbench({
  fixture,
  state = "ready",
}: {
  fixture: DiagnosisFixture;
  state?: "ready" | "empty" | "error";
}) {
  const [skills, setSkills] = useState(fixture.candidate.skills);
  const [projects, setProjects] = useState<ProjectEntry[]>(
    fixture.candidate.projects,
  );
  const [userCorrections, setUserCorrections] = useState<UserCorrection[]>(
    fixture.candidate.userCorrections,
  );
  const [editing, setEditing] = useState<string | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<ChangeItem | null>(
    null,
  );
  const [reportScore, setReportScore] = useState(fixture.report.overallScore);
  const [recalculating, setRecalculating] = useState(false);
  const [editingProjectId, setEditingProjectId] = useState<string | null>(null);
  const [projectDraft, setProjectDraft] = useState("");
  const [editingProjectText, setEditingProjectText] = useState("");

  if (state === "error")
    return (
      <AppShell>
        <FixtureState
          errorText="候选人或岗位版本数据暂时不可用。"
          state="error"
        />
      </AppShell>
    );
  if (state === "empty")
    return (
      <AppShell>
        <FixtureState
          emptyText="上传简历或录入技能后开始诊断。"
          state="empty"
        />
      </AppShell>
    );

  const context: JobUpdateContext = {
    baselineVersion: fixture.job.version,
    jobTitle: fixture.job.title,
    targetVersion: fixture.job.version,
    timeWindow: fixture.job.window,
  };
  const reportEvidence: ChangeItem = {
    id: fixture.report.matchId,
    kind: "modified",
    title: "匹配依据",
    detail: "岗位版本与候选人证据共同决定本次匹配结果。",
    confidence: fixture.report.overallScore,
    status: "accepted",
    evidence: fixture.report.evidence,
  };
  const counts = {
    ready: skills.filter((skill) => skill.status === "ready").length,
    partial: skills.filter((skill) => skill.status === "partial").length,
    missing: skills.filter((skill) => skill.status === "missing").length,
  };

  function pushCorrection(correction: UserCorrection) {
    setUserCorrections((current) => [...current, correction]);
  }

  function updateSkill(index: number, patch: Partial<SkillMatch>) {
    const before = skills[index]?.status;
    setSkills((current) =>
      current.map((skill, currentIndex) =>
        currentIndex === index ? { ...skill, ...patch } : skill,
      ),
    );
    if (patch.status && before && patch.status !== before) {
      pushCorrection({
        id: makeCorrectionId("corr"),
        timestamp: nowDate(),
        field: "skill_status",
        target: skills[index]?.name ?? `skill-${index}`,
        before,
        after: patch.status,
      });
    }
  }

  function recalculate() {
    setRecalculating(true);
    window.setTimeout(() => {
      const ready = skills.filter((skill) => skill.status === "ready").length;
      const missing = skills.filter(
        (skill) => skill.status === "missing",
      ).length;
      setReportScore(
        Math.max(
          0,
          Math.min(
            1,
            fixture.report.overallScore + (ready - 1) * 0.08 - missing * 0.04,
          ),
        ),
      );
      setRecalculating(false);
    }, 500);
  }

  function addProject() {
    const text = projectDraft.trim();
    if (!text) return;
    const entry: ProjectEntry = { id: makeProjectId(), text };
    setProjects((current) => [...current, entry]);
    pushCorrection({
      id: makeCorrectionId("corr"),
      timestamp: nowDate(),
      field: "project_added",
      target: entry.id,
      after: text,
    });
    setProjectDraft("");
  }

  function saveProjectEdit(id: string) {
    const text = editingProjectText.trim();
    if (!text) return;
    const before = projects.find((p) => p.id === id)?.text;
    setProjects((current) =>
      current.map((p) => (p.id === id ? { ...p, text } : p)),
    );
    if (before !== undefined && before !== text) {
      pushCorrection({
        id: makeCorrectionId("corr"),
        timestamp: nowDate(),
        field: "project_text",
        target: id,
        before,
        after: text,
      });
    }
    setEditingProjectId(null);
    setEditingProjectText("");
  }

  function cancelProjectEdit() {
    setEditingProjectId(null);
    setEditingProjectText("");
  }

  function removeProject(id: string) {
    const before = projects.find((p) => p.id === id)?.text;
    setProjects((current) => current.filter((p) => p.id !== id));
    if (before !== undefined) {
      pushCorrection({
        id: makeCorrectionId("corr"),
        timestamp: nowDate(),
        field: "project_removed",
        target: id,
        before,
      });
    }
    if (editingProjectId === id) cancelProjectEdit();
  }

  return (
    <AppShell>
      <div className="diagnosis-workbench">
        <aside className="diagnosis-profile" aria-label="候选人画像">
          <div className="diagnosis-heading">
            <div>
              <h1>{fixture.candidate.name}</h1>
              <span>{fixture.candidate.headline}</span>
            </div>
            <Tag>演示数据</Tag>
          </div>
          <p className="profile-location">{fixture.candidate.location}</p>
          <div className="profile-counts">
            <span>
              <b>{counts.ready}</b>已具备
            </span>
            <span>
              <b>{counts.partial}</b>部分具备
            </span>
            <span>
              <b>{counts.missing}</b>缺失
            </span>
          </div>
          <h2>技能画像</h2>
          <div className="skill-list">
            {skills.map((skill, index) => (
              <article
                className={`profile-skill profile-skill-${skill.status}`}
                key={skill.name}
              >
                <div>
                  <strong>{skill.name}</strong>
                  <StatusMark status={skillStatusToReview(skill.status)} />
                </div>
                {editing === skill.name ? (
                  <>
                    <Select
                      aria-label={`编辑 ${skill.name}`}
                      defaultValue={skill.status}
                      onChange={(value) =>
                        updateSkill(index, { status: value })
                      }
                      options={SKILL_STATUSES.map((s) => ({
                        label:
                          s === "ready"
                            ? "已具备"
                            : s === "partial"
                              ? "部分具备"
                              : "缺失",
                        value: s,
                      }))}
                    />
                    <Button onClick={() => setEditing(null)} size="small">
                      完成
                    </Button>
                  </>
                ) : (
                  <button
                    onClick={() => setEditing(skill.name)}
                    type="button"
                  >{`${skill.level} · ${skill.years} 年`}</button>
                )}
                <small>{skill.evidence}</small>
              </article>
            ))}
          </div>
          <h2>项目证据</h2>
          <ul className="project-list">
            {projects.map((project) =>
              editingProjectId === project.id ? (
                <li className="project-row-editing" key={project.id}>
                  <Input
                    aria-label={`编辑项目 ${project.id}`}
                    onChange={(event) =>
                      setEditingProjectText(event.target.value)
                    }
                    onPressEnter={() => saveProjectEdit(project.id)}
                    value={editingProjectText}
                  />
                  <Button
                    onClick={() => saveProjectEdit(project.id)}
                    size="small"
                    type="primary"
                  >
                    保存
                  </Button>
                  <Button onClick={cancelProjectEdit} size="small">
                    取消
                  </Button>
                </li>
              ) : (
                <li className="project-row" key={project.id}>
                  <span>{project.text}</span>
                  <span className="project-actions">
                    <Button
                      aria-label={`编辑项目 ${project.id}`}
                      icon={<PencilSimple size={14} />}
                      onClick={() => {
                        setEditingProjectId(project.id);
                        setEditingProjectText(project.text);
                      }}
                      size="small"
                      type="text"
                    />
                    <Button
                      aria-label={`删除项目 ${project.id}`}
                      danger
                      icon={<Trash size={14} />}
                      onClick={() => removeProject(project.id)}
                      size="small"
                      type="text"
                    />
                  </span>
                </li>
              ),
            )}
            <li className="project-row-new">
              <Input
                aria-label="新增项目"
                onChange={(event) => setProjectDraft(event.target.value)}
                onPressEnter={addProject}
                placeholder="新增项目证据 · 回车保存"
                value={projectDraft}
              />
              <Button
                disabled={!projectDraft.trim()}
                icon={<Plus aria-hidden size={14} />}
                onClick={addProject}
                size="small"
                type="primary"
              >
                新增
              </Button>
            </li>
          </ul>
          {userCorrections.length > 0 ? (
            <p className="project-audit-meta">
              {`本次会话已记录 ${userCorrections.length} 条修改（仅本地）`}
            </p>
          ) : null}
        </aside>
        <main className="diagnosis-report" aria-labelledby="diagnosis-title">
          <div className="diagnosis-title">
            <div>
              <h2 id="diagnosis-title">
                {fixture.job.title} <span>{fixture.job.version}</span>
              </h2>
              <p>{`${fixture.job.window} · ${fixture.job.evidenceCount} 条岗位依据`}</p>
            </div>
            <Button aria-label="编辑画像" icon={<PencilSimple />} type="text" />
          </div>
          <section className="match-summary">
            <div>
              <span>匹配总览</span>
              <ConfidenceMeter confidence={reportScore} variant="prominent" />
            </div>
            <div>
              <span>已具备</span>
              <b>{counts.ready}</b>
            </div>
            <div>
              <span>待提升</span>
              <b>{counts.partial + counts.missing}</b>
            </div>
          </section>
          <div className="recalculate-bar">
            <span>修改画像后重新计算匹配报告</span>
            <Button
              loading={recalculating}
              onClick={recalculate}
              size="small"
              type="primary"
            >
              重新计算
            </Button>
          </div>
          <section className="gap-section">
            <SectionHeader
              action={
                <Button
                  onClick={() => setSelectedEvidence(reportEvidence)}
                  size="small"
                  type="link"
                >
                  查看依据
                </Button>
              }
              meta={`${fixture.report.gaps.length} 项`}
              title="关键短板"
            />
            <div className="gap-list">
              {fixture.report.gaps.map((gap) => (
                <article
                  className={`gap-item gap-${gap.priority}`}
                  key={gap.skill}
                >
                  <div>
                    <strong>{gap.skill}</strong>
                    <Tag>{gap.priority === "high" ? ("优先") : ("补强")}</Tag>
                  </div>
                  <p>{gap.reason}</p>
                  <span>{gap.action}</span>
                </article>
              ))}
            </div>
          </section>
          <section className="match-evidence">
            <h3>岗位与候选人依据</h3>
            <p>
              报告同时使用已发布岗位版本和候选人项目证据，不以总分替代技能级判断。
            </p>
            <Button
              onClick={() => setSelectedEvidence(reportEvidence)}
              size="small"
              type="link"
            >
              打开证据
            </Button>
          </section>
        </main>
        <aside className="learning-panel" aria-label="学习路径">
          <div className="section-heading">
            <div className="inline-heading">
              <h2>学习路径</h2>
              <span>按岗位优先级</span>
            </div>
          </div>
          <ol>
            {fixture.report.gaps.map((gap, index) => (
              <li key={gap.skill}>
                <span>{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <strong>{gap.skill}</strong>
                  <p>{gap.action}</p>
                </div>
              </li>
            ))}
          </ol>
          <div className="learning-note">
            <CheckCircle aria-hidden weight="fill" />
            路径会随画像修正重新排序
          </div>
        </aside>
        <EvidenceDrawer
          context={context}
          item={selectedEvidence}
          onClose={() => setSelectedEvidence(null)}
        />
      </div>
    </AppShell>
  );
}