"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  CheckCircle,
  FunnelSimple,
  PencilSimple,
  XCircle,
} from "@phosphor-icons/react";
import { Button, Input, Tag, Tooltip } from "antd";

import { AppShell } from "@/components/app-shell";
import { EvidenceDrawer } from "@/components/evidence-drawer";
import { StatusMark } from "@/components/review-ui";
import { FixtureState } from "@/components/workflow-ui";
import { WorkflowContext } from "@/components/workflow-context";
import type { NewJobsFixture } from "@/lib/new-jobs";
import type {
  ChangeItem,
  JobUpdateContext,
  ReviewStatus,
} from "@/lib/job-update";

type NewJobsWorkbenchProps = {
  fixture: NewJobsFixture;
  state?: "ready" | "empty" | "error";
};

export function NewJobsWorkbench({
  fixture,
  state = "ready",
}: NewJobsWorkbenchProps) {
  const [candidates, setCandidates] = useState(fixture.candidates);
  const [selectedId, setSelectedId] = useState(fixture.candidates[0]?.id ?? "");
  const [query, setQuery] = useState("");
  const [evidenceItem, setEvidenceItem] = useState<ChangeItem | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<EditableCandidate | null>(null);
  const selected =
    candidates.find((candidate) => candidate.id === selectedId) ??
    candidates[0];
  const filtered = useMemo(
    () =>
      candidates.filter((candidate) =>
        `${candidate.title} ${candidate.summary}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [candidates, query],
  );

  if (state === "error")
    return (
      <AppShell>
        <FixtureState errorText="候选岗位来源暂时不可用。" state="error" />
      </AppShell>
    );
  if (state === "empty" || !selected)
    return (
      <AppShell>
        <FixtureState
          action={<Link href="/jobs"><Button type="primary">浏览现有岗位</Button></Link>}
          emptyText="当前时间窗没有新的岗位候选。"
          state="empty"
        />
      </AppShell>
    );

  const context: JobUpdateContext = {
    baselineVersion: "既有岗位库",
    jobTitle: selected.title,
    targetVersion: "候选草稿",
    timeWindow: "2026-05 至 2026-08",
  };

  function updateStatus(status: ReviewStatus) {
    setCandidates((current) =>
      current.map((candidate) =>
        candidate.id === selected.id ? { ...candidate, status } : candidate,
      ),
    );
  }

  function startEditing() {
    setDraft({
      ...selected,
      responsibilities: [...selected.responsibilities],
      requiredSkills: [...selected.requiredSkills],
      preferredSkills: [...selected.preferredSkills],
      scenarios: [...selected.scenarios],
    });
    setEditing(true);
  }

  function cancelEditing() {
    setDraft(null);
    setEditing(false);
  }

  function saveEditing() {
    if (!draft) return;
    setCandidates((current) =>
      current.map((candidate) =>
        candidate.id === draft.id ? draft : candidate,
      ),
    );
    setEditing(false);
  }

  function openEvidence() {
    setEvidenceItem({
      confidence: selected.confidence,
      detail: selected.whyNew,
      evidence: selected.evidence,
      id: selected.id,
      kind: "added",
      status: selected.status,
      title: selected.title,
    });
  }

  return (
    <AppShell>
      <div className="workflow-page">
      <WorkflowContext eyebrow="岗位发现" title={selected.title} stage="确认新岗位定义" next="编辑定义并提交审核" />
      <div className="new-jobs-workbench">
        <aside className="candidate-panel" aria-label="新岗位候选">
          <div className="new-jobs-heading">
            <div>
              <h1>新岗位</h1>
              <span>{`${filtered.length} 个候选`}</span>
            </div>
            <Tag>演示数据</Tag>
          </div>
          <Input
            allowClear
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索候选"
            prefix={<FunnelSimple size={15} />}
            value={query}
          />
          <div className="candidate-list">
            {filtered.map((candidate) => (
              <button
                className={
                  candidate.id === selected.id
                    ? "candidate-item candidate-item-active"
                    : "candidate-item"
                }
                key={candidate.id}
                onClick={() => setSelectedId(candidate.id)}
                type="button"
              >
                <div className="candidate-item-title">
                  <strong>{candidate.title}</strong>
                  <StatusMark status={candidate.status} />
                </div>
                <p>{candidate.summary}</p>
                <span>{`${candidate.companies} 家企业 · ${candidate.sourceCount} 条来源`}</span>
              </button>
            ))}
          </div>
        </aside>

        <main
          className="candidate-definition"
          aria-labelledby="candidate-title"
        >
          <div className="candidate-title-row">
            <div>
              <h2 id="candidate-title">{selected.title}</h2>
              <p>{selected.summary}</p>
            </div>
            <div className="candidate-actions">
              <Tooltip title={editing ? "取消编辑" : "编辑定义"}>
                <Button
                  aria-label="编辑定义"
                  icon={<PencilSimple />}
                  onClick={editing ? cancelEditing : startEditing}
                  size="small"
                  type="text"
                />
              </Tooltip>
            </div>
          </div>

          <div className="candidate-decision" aria-label="候选判断">
            <StatusMark status={selected.status} />
            <span>{`${Math.round(selected.confidence * 100)}% 置信`}</span>
            <span>{`${selected.companies} 家企业`}</span>
            <span>{`${selected.sourceCount} 条来源`}</span>
          </div>

          {editing && draft ? (
            <EditDefinition
              draft={draft}
              onChange={setDraft}
              onCancel={cancelEditing}
              onSave={saveEditing}
            />
          ) : (
            <section
              className="definition-section"
              aria-labelledby="why-new-title"
            >
              <div className="decision-heading">
                <div>
                  <h3 id="why-new-title">为何是新岗位</h3>
                </div>
                <Button onClick={openEvidence} size="small" type="link">
                  查看证据
                </Button>
              </div>
              <p className="why-new">{selected.whyNew}</p>
            </section>
          )}

          {!editing ? (
            <div className="definition-grid">
              <DefinitionBlock
                title="必备技能"
                items={selected.requiredSkills}
                tone="primary"
              />
              <DefinitionBlock
                title="核心职责"
                items={selected.responsibilities}
                tone="primary"
              />
              <DefinitionBlock
                title="加分技能"
                items={selected.preferredSkills}
              />
              <DefinitionBlock title="典型场景" items={selected.scenarios} />
            </div>
          ) : null}

          <footer className="candidate-review-bar">
            <span>{`已检查 ${selected.evidence.length} 条证据；接受后进入岗位定义草稿，仍需人工编辑和发布。`}</span>
            <div>
              <Button
                danger
                icon={<XCircle />}
                onClick={() => updateStatus("rejected")}
                type="text"
              >
                拒绝
              </Button>
              <Button
                icon={<CheckCircle />}
                onClick={() => updateStatus("accepted")}
                type="primary"
              >
                接受候选
              </Button>
            </div>
          </footer>
        </main>
      </div>
      </div>
      <EvidenceDrawer
        context={context}
        item={evidenceItem}
        onClose={() => setEvidenceItem(null)}
      />
    </AppShell>
  );
}

function DefinitionBlock({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone?: "primary";
}) {
  return (
    <section
      className={
        tone ? "definition-block definition-block-primary" : "definition-block"
      }
    >
      <h3>{title}</h3>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

type EditableCandidate = NewJobsFixture["candidates"][number];

function EditDefinition({
  draft,
  onCancel,
  onChange,
  onSave,
}: {
  draft: EditableCandidate;
  onCancel: () => void;
  onChange: (draft: EditableCandidate) => void;
  onSave: () => void;
}) {
  const updateList = (
    key:
      "responsibilities" | "requiredSkills" | "preferredSkills" | "scenarios",
    value: string,
  ) =>
    onChange({
      ...draft,
      [key]: value
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean),
    });
  return (
    <section className="definition-editor" aria-label="编辑岗位定义">
      <label>
        岗位名称
        <Input
          aria-label="岗位名称"
          value={draft.title}
          onChange={(event) =>
            onChange({ ...draft, title: event.target.value })
          }
        />
      </label>
      <label>
        摘要
        <Input.TextArea
          autoSize={{ minRows: 2, maxRows: 4 }}
          aria-label="摘要"
          value={draft.summary}
          onChange={(event) =>
            onChange({ ...draft, summary: event.target.value })
          }
        />
      </label>
      <label>
        为何是新岗位
        <Input.TextArea
          autoSize={{ minRows: 3, maxRows: 5 }}
          aria-label="为何是新岗位"
          value={draft.whyNew}
          onChange={(event) =>
            onChange({ ...draft, whyNew: event.target.value })
          }
        />
      </label>
      <div className="definition-editor-grid">
        <label>
          核心职责
          <Input.TextArea
            autoSize
            aria-label="核心职责"
            value={draft.responsibilities.join("\n")}
            onChange={(event) =>
              updateList("responsibilities", event.target.value)
            }
          />
        </label>
        <label>
          必备技能
          <Input.TextArea
            autoSize
            aria-label="必备技能"
            value={draft.requiredSkills.join("\n")}
            onChange={(event) =>
              updateList("requiredSkills", event.target.value)
            }
          />
        </label>
        <label>
          加分技能
          <Input.TextArea
            autoSize
            aria-label="加分技能"
            value={draft.preferredSkills.join("\n")}
            onChange={(event) =>
              updateList("preferredSkills", event.target.value)
            }
          />
        </label>
        <label>
          典型场景
          <Input.TextArea
            autoSize
            aria-label="典型场景"
            value={draft.scenarios.join("\n")}
            onChange={(event) => updateList("scenarios", event.target.value)}
          />
        </label>
      </div>
      <div className="editor-actions">
        <Button onClick={onCancel}>取消</Button>
        <Button onClick={onSave} type="primary">
          保存定义
        </Button>
      </div>
    </section>
  );
}
