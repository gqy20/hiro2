"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import {
  ArrowClockwise,
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
import { saveCandidateTarget } from "@/lib/api/queries";

const SKILL_STATUSES: Array<SkillMatch["status"]> = [
  "ready",
  "partial",
  "missing",
];

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
  mode = "recruiting",
  state = "ready",
}: {
  fixture: DiagnosisFixture;
  mode?: "recruiting" | "career";
  state?: "ready" | "empty" | "error";
}) {
  const router = useRouter();
  const careerMode = mode === "career";
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
          action={
            <Link href={careerMode ? "/career/jobs" : "/jobs"}>
              <Button type="primary">
                {careerMode ? "选择目标岗位" : "查看岗位"}
              </Button>
            </Link>
          }
          emptyText={
            careerMode
              ? "选择目标岗位并完善画像后开始诊断。"
              : "上传简历或录入技能后开始诊断。"
          }
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
  const requiredGaps = fixture.report.gaps.filter(
    (gap) => gap.priority === "high",
  );
  const priorityGaps =
    requiredGaps.length > 0 ? requiredGaps : fixture.report.gaps;

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
      <div className="workflow-page">
        <div className="diagnosis-workbench">
          <aside className="diagnosis-profile" aria-label="候选人画像">
            <div className="diagnosis-heading">
              <div>
                <h1>{careerMode ? "我的画像" : fixture.candidate.name}</h1>
                <span>
                  {careerMode
                    ? `${fixture.candidate.name} · ${fixture.candidate.headline}`
                    : fixture.candidate.headline}
                </span>
              </div>
              <Link
                className="diagnosis-import-link"
                href={careerMode ? "/profile" : "/resumes"}
              >
                {careerMode ? "编辑画像" : "从简历导入"}
              </Link>
            </div>
            <p className="profile-location">{fixture.candidate.location}</p>
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
                  {!careerMode && editing === skill.name ? (
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
                    <div className="profile-skill-meta">
                      {careerMode ? (
                        <span>
                          {[
                            skill.level,
                            skill.years == null ? "" : `${skill.years} 年`,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </span>
                      ) : (
                        <button
                          onClick={() => setEditing(skill.name)}
                          type="button"
                        >
                          {[
                            skill.level,
                            skill.years == null ? "" : `${skill.years} 年`,
                          ]
                            .filter(Boolean)
                            .join(" · ")}
                        </button>
                      )}
                      <small>{skill.evidence}</small>
                    </div>
                  )}
                </article>
              ))}
            </div>
            <h2>项目证据</h2>
            <ul className="project-list">
              {projects.map((project) =>
                !careerMode && editingProjectId === project.id ? (
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
                    {!careerMode ? (
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
                    ) : null}
                  </li>
                ),
              )}
              {!careerMode ? (
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
              ) : null}
            </ul>
            {!careerMode && userCorrections.length > 0 ? (
              <p className="project-audit-meta">
                {`本次会话已记录 ${userCorrections.length} 条修改（仅本地）`}
              </p>
            ) : null}
          </aside>
          <main className="diagnosis-report" aria-labelledby="diagnosis-title">
            <div className="diagnosis-title">
              <div>
                <span className="career-kicker">目标岗位</span>
                <Select
                  aria-label="选择目标岗位"
                  className="career-target-select"
                  onChange={async (version) => {
                    await saveCandidateTarget(fixture.candidate.id, version);
                    const route = careerMode
                      ? "/career/diagnosis"
                      : "/diagnosis";
                    router.push(
                      `${route}?candidate=${encodeURIComponent(fixture.candidate.id)}&job=${encodeURIComponent(version)}`,
                    );
                  }}
                  options={(
                    fixture.targetJobs ?? [
                      {
                        version: fixture.job.version,
                        title: fixture.job.title,
                      },
                    ]
                  ).map((job) => ({
                    label: `${job.title} · ${job.version}`,
                    value: job.version,
                  }))}
                  value={fixture.job.version}
                />
                <p>{`${fixture.job.version} · 已发布岗位标准`}</p>
              </div>
              <span className="diagnosis-title-actions">
                {careerMode ? (
                  <Button href="/profile" icon={<PencilSimple />} type="text">
                    编辑画像
                  </Button>
                ) : null}
                <Button
                  icon={<ArrowClockwise />}
                  loading={recalculating}
                  onClick={recalculate}
                  size="small"
                  type="primary"
                >
                  重新计算
                </Button>
              </span>
            </div>
            <section className="match-summary">
              <div>
                {careerMode && fixture.report.requiredTotal ? (
                  <>
                    <span>必备能力</span>
                    <b>
                      {fixture.report.requiredMet ?? 0} /{" "}
                      {fixture.report.requiredTotal}
                    </b>
                    <small>投递基础 {Math.round(reportScore * 100)}%</small>
                  </>
                ) : (
                  <>
                    <span>投递基础</span>
                    <ConfidenceMeter
                      confidence={reportScore}
                      variant="prominent"
                    />
                  </>
                )}
              </div>
              <div>
                <span>已具备</span>
                <b>{counts.ready}</b>
              </div>
              {careerMode ? (
                <>
                  <div>
                    <span>部分具备</span>
                    <b>{counts.partial}</b>
                  </div>
                  <div>
                    <span>缺失</span>
                    <b>{counts.missing}</b>
                  </div>
                </>
              ) : null}
              <div>
                <span>优先补齐</span>
                <b>{priorityGaps.length}</b>
              </div>
            </section>
            <p className="recalculate-hint">画像更新后，重新判断你的投递基础</p>
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
                meta={`${priorityGaps.length} 项优先处理`}
                title="先补什么"
              />
              <div className="gap-list">
                {priorityGaps.map((gap) => (
                  <article
                    className={`gap-item gap-${gap.priority}`}
                    key={gap.skill}
                  >
                    <div>
                      <strong>{gap.skill}</strong>
                      <Tag>{gap.priority === "high" ? "优先" : "补强"}</Tag>
                    </div>
                    <p>
                      {gap.reason ||
                        "岗位要求中尚未找到你的有效项目或技能证明。"}
                    </p>
                    <span>{gap.action}</span>
                  </article>
                ))}
              </div>
            </section>
            <section className="match-evidence">
              <div className="match-evidence-heading">
                <h3>为什么这样判断</h3>
                <Button
                  onClick={() => setSelectedEvidence(reportEvidence)}
                  size="small"
                  type="link"
                >
                  打开证据
                </Button>
              </div>
              <p>
                结果同时依据已发布岗位标准和你的技能、项目证据，不以单一分数决定是否适合投递。
              </p>
            </section>
          </main>
          <aside
            className="learning-panel"
            aria-label={careerMode ? "后续行动" : "诊断要点"}
          >
            <div className="section-heading">
              <div className="inline-heading">
                <h2>{careerMode ? "后续行动" : "诊断要点"}</h2>
                <span>{`${priorityGaps.length} 项待关注`}</span>
              </div>
            </div>
            {careerMode ? (
              <div className="career-diagnosis-next">
                <strong>按优先级补齐能力缺口</strong>
                <p>学习路径集中展示知识、练习、评测和能力证明。</p>
                <Link href="/career/path">
                  <Button block type="primary">
                    查看学习路径
                  </Button>
                </Link>
              </div>
            ) : (
              <ul className="recruiting-diagnosis-points">
                {priorityGaps.map((gap) => (
                  <li key={gap.skill}>
                    <strong>{gap.skill}</strong>
                    <span>{gap.reason || "候选人画像中暂无明确证明"}</span>
                  </li>
                ))}
              </ul>
            )}
          </aside>
          <EvidenceDrawer
            context={context}
            item={selectedEvidence}
            onClose={() => setSelectedEvidence(null)}
          />
        </div>
      </div>
    </AppShell>
  );
}
