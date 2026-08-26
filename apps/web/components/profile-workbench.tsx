"use client";

import { useState } from "react";
import Link from "next/link";
import { Button, Input, Select } from "antd";
import type { DiagnosisFixture } from "@/lib/diagnosis";
import { saveCandidateProfile } from "@/lib/api/queries";

export function ProfileWorkbench({ fixture }: { fixture: DiagnosisFixture }) {
  const [skills, setSkills] = useState(fixture.candidate.skills);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  async function save() {
    setSaving(true);
    await saveCandidateProfile(fixture.candidate.id, skills.map(({ name, status }) => ({ name, status })), fixture.candidate.projects.map((project) => project.text));
    setSaved(true);
    setSaving(false);
  }
  return <section className="profile-workspace" aria-labelledby="profile-title"><header className="page-heading"><div><p className="profile-target-context">目标岗位：{fixture.job.title} · {fixture.job.version}</p><h1 id="profile-title">我的画像</h1><p>这些信息会用于目标岗位诊断，你可以随时修正。</p></div><span className="profile-save-actions"><Button loading={saving} onClick={save} type="primary">保存并重新诊断</Button>{saved ? <Link href="/diagnosis">查看新结果</Link> : null}</span></header><div className="profile-workspace-grid"><section><h2>技能与熟练度</h2>{skills.map((skill, index) => <div className="profile-edit-row" key={skill.name}><strong>{skill.name}</strong><Select aria-label={`编辑 ${skill.name}`} value={skill.status} onChange={(value) => setSkills((current) => current.map((item, i) => i === index ? { ...item, status: value } : item))} options={[{label:"已具备",value:"ready"},{label:"部分具备",value:"partial"},{label:"缺失",value:"missing"}]} /><span>{skill.level}{skill.years == null ? "" : ` · ${skill.years} 年`}</span></div>)}</section><section><h2>能力证明</h2>{fixture.candidate.projects.map((project) => <div className="profile-project-row" key={project.id}><strong>{project.text}</strong></div>)}<Input.TextArea aria-label="新增能力证明" placeholder="新增项目、作品或评测结果" /><Button type="link">添加能力证明</Button></section></div></section>;
}
