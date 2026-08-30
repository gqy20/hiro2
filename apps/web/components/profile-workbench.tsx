"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, MagnifyingGlass } from "@phosphor-icons/react";
import {
  Button,
  Drawer,
  Empty,
  Input,
  InputNumber,
  Segmented,
  Select,
  Tag,
} from "antd";

import { addCandidateProof, saveCandidateProfile } from "@/lib/api/queries";
import type { DiagnosisFixture, SkillMatch } from "@/lib/diagnosis";

type SkillFilter = "全部" | "已具备" | "需确认";

const STATUS_META: Record<
  SkillMatch["status"],
  { color: string; label: string }
> = {
  ready: { color: "green", label: "已具备" },
  partial: { color: "orange", label: "部分具备" },
  missing: { color: "red", label: "缺失" },
};

export function ProfileWorkbench({ fixture }: { fixture: DiagnosisFixture }) {
  const router = useRouter();
  const [skills, setSkills] = useState(fixture.candidate.skills);
  const [projects, setProjects] = useState(fixture.candidate.projects);
  const [proofDraft, setProofDraft] = useState("");
  const [filter, setFilter] = useState<SkillFilter>("全部");
  const [query, setQuery] = useState("");
  const [editingSkill, setEditingSkill] = useState<SkillMatch | null>(null);
  const [proofTitle, setProofTitle] = useState("");
  const [proofDescription, setProofDescription] = useState("");
  const [proofSaving, setProofSaving] = useState(false);
  const [proofSaved, setProofSaved] = useState(false);
  const [dirtySkills, setDirtySkills] = useState<string[]>([]);
  const [projectsDirty, setProjectsDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const needsReview = skills.filter((skill) => skill.status !== "ready").length;
  const changeCount = dirtySkills.length + (projectsDirty ? 1 : 0);
  const visibleSkills = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase();
    return skills.filter((skill) => {
      const matchesFilter =
        filter === "全部" ||
        (filter === "已具备" && skill.status === "ready") ||
        (filter === "需确认" && skill.status !== "ready");
      return (
        matchesFilter &&
        (!normalizedQuery ||
          skill.name.toLocaleLowerCase().includes(normalizedQuery))
      );
    });
  }, [filter, query, skills]);

  async function save() {
    setSaving(true);
    setError("");
    try {
      await saveCandidateProfile(
        fixture.candidate.id,
        skills.map(({ name, status, level, years }) => ({
          name,
          status,
          level,
          years,
        })),
        projects.map((project) => project.text),
      );
      router.push(
        `/career/diagnosis?job=${encodeURIComponent(fixture.job.version)}`,
      );
    } catch (cause) {
      setError(
        `保存失败：${cause instanceof Error ? cause.message : "未知错误"}`,
      );
    } finally {
      setSaving(false);
    }
  }

  function addProjectProof() {
    const text = proofDraft.trim();
    if (!text) return;
    setProjects((current) => [
      ...current,
      { id: `profile-${Date.now().toString(36)}`, text },
    ]);
    setProofDraft("");
    setProjectsDirty(true);
  }

  function openSkill(skill: SkillMatch) {
    setEditingSkill({ ...skill });
    setProofTitle("");
    setProofDescription("");
    setProofSaved(false);
  }

  function applySkillChange() {
    if (!editingSkill) return;
    setSkills((current) =>
      current.map((skill) =>
        skill.name === editingSkill.name ? editingSkill : skill,
      ),
    );
    setDirtySkills((current) =>
      current.includes(editingSkill.name)
        ? current
        : [...current, editingSkill.name],
    );
    setEditingSkill(null);
  }

  async function addSkillProof() {
    if (!editingSkill?.skillId || !proofTitle.trim()) return;
    setProofSaving(true);
    setError("");
    try {
      await addCandidateProof(fixture.candidate.id, {
        skillId: editingSkill.skillId,
        title: proofTitle.trim(),
        description: proofDescription.trim(),
      });
      setProofSaved(true);
      setProofTitle("");
      setProofDescription("");
    } catch (cause) {
      setError(
        `证明添加失败：${cause instanceof Error ? cause.message : "未知错误"}`,
      );
    } finally {
      setProofSaving(false);
    }
  }

  return (
    <section className="profile-workspace" aria-labelledby="profile-title">
      <header className="profile-header">
        <div>
          <h1 id="profile-title" className="sr-only">
            我的画像
          </h1>
          <p>{`${fixture.job.title} · ${fixture.job.version} · 修改后重新计算诊断`}</p>
        </div>
        <div className="profile-save-actions">
          {changeCount > 0 ? <span>{`${changeCount} 项待保存`}</span> : null}
          <Button
            disabled={changeCount === 0}
            loading={saving}
            onClick={() => void save()}
            type="primary"
          >
            保存更改并重新诊断
          </Button>
        </div>
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
        <section className="profile-skill-panel">
          <div className="profile-section-heading">
            <div>
              <h2>技能画像</h2>
              <span>{`${visibleSkills.length} / ${skills.length} 项`}</span>
            </div>
            <Segmented<SkillFilter>
              onChange={setFilter}
              options={["全部", "已具备", "需确认"]}
              size="small"
              value={filter}
            />
          </div>
          <Input
            allowClear
            aria-label="搜索技能"
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索技能"
            prefix={<MagnifyingGlass aria-hidden size={15} />}
            value={query}
          />
          <div className="profile-skill-scroll">
            {visibleSkills.length === 0 ? (
              <Empty
                description="没有符合条件的技能"
                image={Empty.PRESENTED_IMAGE_SIMPLE}
              />
            ) : (
              visibleSkills.map((skill) => {
                const status = STATUS_META[skill.status];
                return (
                  <button
                    className="profile-skill-row"
                    key={skill.name}
                    onClick={() => openSkill(skill)}
                    type="button"
                  >
                    <span className="profile-skill-copy">
                      <strong>{skill.name}</strong>
                      <span>{`${skill.evidence || "来源未登记"} · ${skill.skillId ? "已标准化" : "待确认映射"}`}</span>
                    </span>
                    <span className="profile-skill-level">
                      {skill.level}
                      {skill.years == null ? "" : ` · ${skill.years} 年`}
                    </span>
                    <Tag color={status.color}>{status.label}</Tag>
                    <ArrowRight aria-hidden size={16} />
                  </button>
                );
              })
            )}
          </div>
        </section>

        <section className="profile-proof-panel">
          <div className="profile-section-heading">
            <div>
              <h2>能力证明</h2>
              <span>{`${projects.length} 项`}</span>
            </div>
          </div>
          <div className="profile-project-scroll">
            {projects.map((project) => (
              <div className="profile-project-row" key={project.id}>
                <strong>{project.text}</strong>
              </div>
            ))}
          </div>
          <div className="profile-proof-compose">
            <Input.TextArea
              aria-label="新增能力证明"
              onChange={(event) => setProofDraft(event.target.value)}
              placeholder="新增项目、作品或评测结果"
              rows={3}
              value={proofDraft}
            />
            <Button
              disabled={!proofDraft.trim()}
              onClick={addProjectProof}
              type="link"
            >
              添加能力证明
            </Button>
          </div>
        </section>
      </div>

      {error ? (
        <p className="profile-error" role="alert">
          {error}
        </p>
      ) : null}

      <Drawer
        onClose={() => setEditingSkill(null)}
        open={editingSkill !== null}
        size="large"
        title={editingSkill?.name ?? "技能详情"}
      >
        {editingSkill ? (
          <div className="profile-skill-detail">
            <section>
              <h3>技能判断</h3>
              <div className="profile-skill-form">
                <label>
                  <span>当前状态</span>
                  <Select
                    aria-label="当前状态"
                    onChange={(status) =>
                      setEditingSkill((current) =>
                        current
                          ? {
                              ...current,
                              status,
                              level:
                                status === "partial"
                                  ? "初级"
                                  : status === "ready" &&
                                      current.level === "初级"
                                    ? "中级"
                                    : current.level,
                            }
                          : current,
                      )
                    }
                    options={Object.entries(STATUS_META).map(
                      ([value, meta]) => ({
                        label: meta.label,
                        value,
                      }),
                    )}
                    value={editingSkill.status}
                  />
                </label>
                <label>
                  <span>熟练度</span>
                  <Select
                    aria-label="熟练度"
                    onChange={(level) =>
                      setEditingSkill((current) =>
                        current ? { ...current, level } : current,
                      )
                    }
                    options={["初级", "中级", "高级"].map((value) => ({
                      label: value,
                      value,
                    }))}
                    value={editingSkill.level}
                  />
                </label>
                <label>
                  <span>使用年限</span>
                  <div className="profile-years-input">
                    <InputNumber
                      aria-label="使用年限"
                      max={60}
                      min={0}
                      onChange={(years) =>
                        setEditingSkill((current) =>
                          current ? { ...current, years } : current,
                        )
                      }
                      precision={1}
                      value={editingSkill.years}
                    />
                    <span>年</span>
                  </div>
                </label>
              </div>
              <dl className="profile-skill-facts">
                <div>
                  <dt>识别来源</dt>
                  <dd>{editingSkill.evidence || "未登记"}</dd>
                </div>
                <div>
                  <dt>标准映射</dt>
                  <dd>{editingSkill.skillId ? "已完成" : "待确认"}</dd>
                </div>
              </dl>
              <details>
                <summary>处理信息</summary>
                <p>{`能力域：${editingSkill.skillId || "未映射"}`}</p>
                <p>{`技能点：${editingSkill.pointId || "未映射"}`}</p>
              </details>
            </section>

            <section>
              <h3>补充能力证明</h3>
              <p>把项目、作品或评测结果关联到这项技能，诊断会使用这些证明。</p>
              {editingSkill.skillId ? (
                <>
                  <Input
                    aria-label="证明标题"
                    onChange={(event) => setProofTitle(event.target.value)}
                    placeholder="证明标题"
                    value={proofTitle}
                  />
                  <Input.TextArea
                    aria-label="证明说明"
                    onChange={(event) =>
                      setProofDescription(event.target.value)
                    }
                    placeholder="你完成了什么，结果如何"
                    rows={3}
                    value={proofDescription}
                  />
                  <Button
                    disabled={!proofTitle.trim()}
                    loading={proofSaving}
                    onClick={() => void addSkillProof()}
                  >
                    添加到该技能
                  </Button>
                  {proofSaved ? <Tag color="green">证明已添加</Tag> : null}
                </>
              ) : (
                <p>该技能尚未完成标准映射，暂时不能关联结构化证明。</p>
              )}
            </section>

            <footer>
              <Button onClick={() => setEditingSkill(null)}>取消</Button>
              <Button onClick={applySkillChange} type="primary">
                应用技能修改
              </Button>
            </footer>
          </div>
        ) : null}
      </Drawer>
    </section>
  );
}
