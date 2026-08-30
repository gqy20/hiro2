"use client";

import { useState } from "react";
import Link from "next/link";
import { Button, Input, Select } from "antd";
import type { DiagnosisFixture } from "@/lib/diagnosis";
import { saveCandidateProfile } from "@/lib/api/queries";

export function ProfileWorkbench({ fixture }: { fixture: DiagnosisFixture }) {
  const [skills, setSkills] = useState(fixture.candidate.skills);
  const [projects, setProjects] = useState(fixture.candidate.projects);
  const [proofDraft, setProofDraft] = useState("");
  const [showAllSkills, setShowAllSkills] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  async function save() {
    setSaving(true);
    await saveCandidateProfile(
      fixture.candidate.id,
      skills.map(({ name, status }) => ({ name, status })),
      projects.map((project) => project.text),
    );
    setSaved(true);
    setSaving(false);
  }
  const visibleSkills = showAllSkills ? skills : skills.slice(0, 12);
  const needsReview = skills.filter((skill) => skill.status !== "ready").length;

  function addProof() {
    const text = proofDraft.trim();
    if (!text) return;
    setProjects((current) => [
      ...current,
      { id: `profile-${Date.now().toString(36)}`, text },
    ]);
    setProofDraft("");
    setSaved(false);
  }
  return (
    <section className="profile-workspace" aria-labelledby="profile-title">
      <header className="page-heading">
        <div>
          <h1 id="profile-title" className="sr-only">
            我的画像
          </h1>
          <p>{`${fixture.job.title} · ${fixture.job.version} · 修改后重新计算诊断`}</p>
        </div>
        <span className="profile-save-actions">
          <Button loading={saving} onClick={save} type="primary">
            保存并重新诊断
          </Button>
          {saved ? <Link href="/career/diagnosis">查看新结果</Link> : null}
        </span>
      </header>
      <div className="profile-summary" aria-label="画像摘要">
        <div>
          <span>技能记录</span>
          <strong>{skills.length}</strong>
        </div>
        <div>
          <span>能力证明</span>
          <strong>{projects.length}</strong>
        </div>
        <div>
          <span>需确认</span>
          <strong>{needsReview}</strong>
        </div>
      </div>
      <div className="profile-workspace-grid">
        <section>
          <div className="profile-section-heading">
            <h2>技能与熟练度</h2>
            <span>{showAllSkills ? `全部 ${skills.length}` : "常用技能"}</span>
          </div>
          {visibleSkills.map((skill, index) => (
            <div className="profile-edit-row" key={skill.name}>
              <strong>{skill.name}</strong>
              <Select
                aria-label={`编辑 ${skill.name}`}
                value={skill.status}
                onChange={(value) =>
                  setSkills((current) =>
                    current.map((item, i) =>
                      i === index ? { ...item, status: value } : item,
                    ),
                  )
                }
                options={[
                  { label: "已具备", value: "ready" },
                  { label: "部分具备", value: "partial" },
                  { label: "缺失", value: "missing" },
                ]}
              />
              <span>
                {skill.level}
                {skill.years == null ? "" : ` · ${skill.years} 年`}
              </span>
            </div>
          ))}
          {skills.length > 12 ? (
            <Button
              onClick={() => setShowAllSkills((current) => !current)}
              type="link"
            >
              {showAllSkills ? "收起技能" : `查看全部 ${skills.length} 项技能`}
            </Button>
          ) : null}
        </section>
        <section>
          <h2>能力证明</h2>
          {projects.map((project) => (
            <div className="profile-project-row" key={project.id}>
              <strong>{project.text}</strong>
            </div>
          ))}
          <Input.TextArea
            aria-label="新增能力证明"
            onChange={(event) => setProofDraft(event.target.value)}
            placeholder="新增项目、作品或评测结果"
            value={proofDraft}
          />
          <Button disabled={!proofDraft.trim()} onClick={addProof} type="link">
            添加能力证明
          </Button>
        </section>
      </div>
    </section>
  );
}
