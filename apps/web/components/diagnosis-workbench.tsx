"use client";

import { useState } from "react";
import { CheckCircle, PencilSimple } from "@phosphor-icons/react";
import { Button, Input, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { EvidenceDrawer } from "@/components/evidence-drawer";
import { ConfidenceMeter, StatusMark } from "@/components/review-ui";
import { FixtureState, skillStatusToReview } from "@/components/workflow-ui";
import type { DiagnosisFixture, SkillMatch } from "@/lib/diagnosis";
import type { ChangeItem, JobUpdateContext } from "@/lib/job-update";

export function DiagnosisWorkbench({
  fixture,
  state = "ready",
}: {
  fixture: DiagnosisFixture;
  state?: "ready" | "empty" | "error";
}) {
  const [skills, setSkills] = useState(fixture.candidate.skills);
  const [editing, setEditing] = useState<string | null>(null);
  const [selectedEvidence, setSelectedEvidence] = useState<ChangeItem | null>(
    null,
  );
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

  function updateSkill(index: number, patch: Partial<SkillMatch>) {
    setSkills((current) =>
      current.map((skill, currentIndex) =>
        currentIndex === index ? { ...skill, ...patch } : skill,
      ),
    );
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
                    <Input
                      aria-label={`编辑 ${skill.name}`}
                      defaultValue={`${skill.level} · ${skill.years} 年`}
                      onPressEnter={(event) => {
                        updateSkill(index, {
                          evidence: event.currentTarget.value,
                        });
                        setEditing(null);
                      }}
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
            {fixture.candidate.projects.map((project) => (
              <li key={project}>{project}</li>
            ))}
          </ul>
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
              <ConfidenceMeter confidence={fixture.report.overallScore} />
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
          <section className="gap-section">
            <div className="section-heading">
              <div className="inline-heading">
                <h3>关键短板</h3>
                <span>{`${fixture.report.gaps.length} 项`}</span>
              </div>
              <Button
                onClick={() => setSelectedEvidence(reportEvidence)}
                size="small"
                type="link"
              >
                查看依据
              </Button>
            </div>
            <div className="gap-list">
              {fixture.report.gaps.map((gap) => (
                <article
                  className={`gap-item gap-${gap.priority}`}
                  key={gap.skill}
                >
                  <div>
                    <strong>{gap.skill}</strong>
                    <Tag>{gap.priority === "high" ? "优先" : "补强"}</Tag>
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
