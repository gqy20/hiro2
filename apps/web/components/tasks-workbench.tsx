"use client";

import { useMemo, useState } from "react";
import { ArrowSquareOut, CheckCircle, Flag, XCircle } from "@phosphor-icons/react";
import { Button, Empty, Input, Select, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { WorkflowContext } from "@/components/workflow-context";
import { SectionHeader } from "@/components/workflow-ui";
import {
  buildMockTasks,
  REVIEW_PRIORITY_TONES,
  REVIEW_STATUS_TONES,
  TASK_TYPE_LABELS,
  type ReviewDecision,
  type ReviewTask,
  type ReviewTaskStatus,
} from "@/lib/tasks-fixture";

const STATUS_LABEL: Record<ReviewTaskStatus, string> = {
  PENDING: "待领取",
  CLAIMED: "已领取",
  IN_REVIEW: "审核中",
  SUBMITTED: "已提交",
  ADJUDICATING: "复核中",
  RESOLVED: "已解决",
};

const DECISION_OPTIONS: Array<{ value: ReviewDecision; label: string }> = [
  { value: "ACCEPT", label: "接受" },
  { value: "MODIFY", label: "修改" },
  { value: "REJECT", label: "拒绝" },
  { value: "UNKNOWN", label: "待定" },
];

function SystemOutputView({ output }: { output: Record<string, unknown> }) {
  return (
    <dl className="tasks-system-output">
      {Object.entries(output).map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{typeof value === "object" ? JSON.stringify(value) : String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

export function TasksWorkbench() {
  const [tasks, setTasks] = useState<ReviewTask[]>(() => buildMockTasks());
  const [selectedId, setSelectedId] = useState<string | null>(
    () => tasks[0]?.task_id ?? null,
  );
  const [decision, setDecision] = useState<ReviewDecision>("ACCEPT");
  const [rationale, setRationale] = useState("");

  const selected = useMemo(
    () => tasks.find((t) => t.task_id === selectedId) ?? null,
    [tasks, selectedId],
  );

  function transitionTo(
    id: string,
    next: ReviewTaskStatus,
    decisions: { decision: ReviewDecision; rationale: string } | null = null,
  ) {
    setTasks((current) =>
      current.map((t) =>
        t.task_id === id
          ? {
              ...t,
              status: next,
              assignee_id:
                next === "PENDING"
                  ? null
                  : (t.assignee_id ?? "reviewer-current"),
              system_output: decisions
                ? {
                    ...t.system_output,
                    last_decision: decisions.decision,
                    last_rationale: decisions.rationale,
                  }
                : t.system_output,
            }
          : t,
      ),
    );
  }

  function handleSubmit() {
    if (!selected) return;
    transitionTo(selected.task_id, "SUBMITTED", { decision, rationale });
    setRationale("");
  }

  function handleClaim() {
    if (!selected) return;
    transitionTo(selected.task_id, "IN_REVIEW");
  }

  function handleResolve() {
    if (!selected) return;
    transitionTo(selected.task_id, "RESOLVED", { decision, rationale });
  }

  return (
    <AppShell>
      <div className="workflow-page">
      <WorkflowContext eyebrow="审核工作区" title="我的任务" stage="处理待审核事项" next="领取一项任务" href="#task-workspace" />
      <section className="tasks-workbench" id="task-workspace" aria-labelledby="tasks-title">
        <header className="page-heading">
          <h1 id="tasks-title">我的任务</h1>
          <p>
            {`${tasks.length} 条任务 · F-T4.10 任务列表 + F-T4.11 审核工作区`}
          </p>
        </header>

        <div className="tasks-layout">
          <aside
            aria-label="任务列表"
            className="tasks-list"
          >
            <SectionHeader meta={`${tasks.length} 条`} title="待处理任务" />
            <ul>
              {tasks.map((t) => (
                <li
                  className={`tasks-list-item ${
                    t.task_id === selectedId ? "is-active" : ""
                  }`}
                  key={t.task_id}
                >
                  <button
                    className="tasks-list-button"
                    onClick={() => setSelectedId(t.task_id)}
                    type="button"
                  >
                    <div className="tasks-list-meta">
                      <Tag color={REVIEW_PRIORITY_TONES[t.priority]}>
                        {t.priority === "high"
                          ? "优先"
                          : t.priority === "medium"
                            ? "补强"
                            : "低"}
                      </Tag>
                      <Tag color={REVIEW_STATUS_TONES[t.status]}>
                        {STATUS_LABEL[t.status]}
                      </Tag>
                      {t.needs_dual_review ? (
                        <Tag color="purple">需双审</Tag>
                      ) : null}
                    </div>
                    <strong>{TASK_TYPE_LABELS[t.task_type]}</strong>
                    <small>
                      {`${t.source_record_id} · ${t.run_id}`}
                    </small>
                  </button>
                </li>
              ))}
            </ul>
          </aside>

          <section
            aria-label="审核工作区"
            className="tasks-workspace"
          >
            {selected ? (
              <>
                <div className="tasks-workspace-header">
                  <Tag color={REVIEW_STATUS_TONES[selected.status]}>
                    {STATUS_LABEL[selected.status]}
                  </Tag>
                  <h2>{TASK_TYPE_LABELS[selected.task_type]}</h2>
                  <span>{`source ${selected.source_record_id}`}</span>
                </div>
                <div className="tasks-workspace-meta">
                  <span>
                    {`run_id ${selected.run_id} · 数据集 ${selected.dataset_version}`}
                  </span>
                  <span>{`${selected.evidence_ids.length} 条证据`}</span>
                  {selected.needs_dual_review ? (
                    <span className="tasks-workspace-meta-warn">
                      20% 双人复核规则：此任务需双审
                    </span>
                  ) : null}
                </div>

                <section
                  aria-label="系统结果"
                  className="tasks-workspace-section"
                >
                  <SectionHeader title="系统结果（不可编辑）" />
                  <SystemOutputView output={selected.system_output} />
                </section>

                <section
                  aria-label="证据"
                  className="tasks-workspace-section"
                >
                  <SectionHeader
                    meta={`${selected.evidence_ids.length} 条`}
                    title="证据"
                  />
                  <ul className="tasks-evidence-list">
                    {selected.evidence_ids.map((id) => (
                      <li key={id}>
                        <code>{id}</code>
                      </li>
                    ))}
                  </ul>
                </section>

                <section
                  aria-label="人工决策"
                  className="tasks-workspace-section"
                >
                  <SectionHeader title="人工决策" />
                  <div className="tasks-decision">
                    <Select
                      onChange={(v) => setDecision(v as ReviewDecision)}
                      options={DECISION_OPTIONS}
                      style={{ minWidth: 160 }}
                      value={decision}
                    />
                    <Input
                      aria-label="决策理由"
                      onChange={(e) => setRationale(e.target.value)}
                      placeholder="决策理由（可选）"
                      value={rationale}
                    />
                  </div>
                </section>

                <div className="tasks-workspace-actions">
                  {selected.status === "PENDING" ? (
                    <Button
                      icon={<Flag aria-hidden size={15} />}
                      onClick={handleClaim}
                      type="primary"
                    >
                      领取
                    </Button>
                  ) : null}
                  {selected.status === "IN_REVIEW" ||
                  selected.status === "CLAIMED" ? (
                    <Button
                      icon={<CheckCircle aria-hidden size={15} />}
                      loading={false}
                      onClick={handleSubmit}
                      type="primary"
                    >
                      提交
                    </Button>
                  ) : null}
                  {selected.status === "SUBMITTED" ||
                  selected.status === "ADJUDICATING" ? (
                    <Button
                      icon={<CheckCircle aria-hidden size={15} />}
                      onClick={handleResolve}
                      type="primary"
                    >
                      完成
                    </Button>
                  ) : null}
                  <span className="tasks-workspace-state-meta">
                    {`当前状态：${STATUS_LABEL[selected.status]}`}
                  </span>
                </div>
              </>
            ) : (
              <Empty description="暂无任务，请先领取。" />
            )}
          </section>
        </div>
      </section>
      </div>
    </AppShell>
  );
}

export { XCircle as _XCircle, ArrowSquareOut as _ArrowSquareOut };
