"use client";

import { useMemo, useState } from "react";
import {
  ArrowSquareOut,
  CheckCircle,
  Flag,
  XCircle,
} from "@phosphor-icons/react";
import { Button, Empty, Input, message, Segmented, Select, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { EvidenceBrowser } from "@/components/evidence-browser";
import { SectionHeader } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type {
  EvidenceFacets,
  EvidenceSearchResult,
} from "@/lib/evidence-search";
import { skillLabel } from "@/lib/skill-labels";
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

const FIELD_LABELS: Record<string, string> = {
  predicted_position: "系统映射岗位",
  mapping_method: "映射方式",
  domain_judgment: "系统判断",
  judgment_reason: "判断理由",
  event_date: "事件日期",
  event_type: "事件类型",
  fact_grade: "事实等级",
  skill_mentions: "技能提及",
  skill_id: "能力域",
  predicted_direction: "预测方向",
  confidence: "置信度",
  horizon_days: "预测周期",
  as_of_date: "观察日期",
  current_phase: "当前阶段",
  reason_summary: "判断理由",
  change_type: "变化类型",
  evidence_summary: "证据摘要",
  proposed_level: "建议等级",
};

const TASK_QUESTIONS: Record<ReviewTask["task_type"], string> = {
  jd_annotation: "JD 内容标注是否准确？",
  role_level: "系统岗位映射是否准确？",
  skill_mapping: "事件类型、事实等级和技能提及是否准确？",
  evidence_audit: "系统的岗位领域判断是否准确？",
  forecast_review: "趋势预测是否有足够证据支持？",
  job_review: "岗位能力变化是否应该被采纳？",
  match_review: "人岗匹配判断是否准确？",
  ux_test: "体验验收结果是否符合预期？",
};

function taskSubject(task: ReviewTask): string {
  const title = String(task.system_output.title ?? "").trim();
  if (title) return title;
  const skillId = String(task.system_output.skill_id ?? "").trim();
  if (skillId) return skillLabel(skillId);
  return TASK_TYPE_LABELS[task.task_type];
}

function taskQuestion(task: ReviewTask): string {
  return String(task.system_output.question ?? TASK_QUESTIONS[task.task_type]);
}

function outputValue(key: string, value: unknown): string {
  if (key === "skill_id") return skillLabel(String(value));
  if (key === "confidence") return `${Math.round(Number(value) * 100)}%`;
  if (key === "horizon_days") return `${value} 天`;
  if (key === "domain_judgment") {
    return String(value).toLowerCase() === "true"
      ? "属于相关岗位"
      : "不属于相关岗位";
  }
  if (key === "predicted_direction") {
    return (
      { up: "上升", down: "下降", flat: "平稳" }[String(value)] ?? String(value)
    );
  }
  if (key === "mapping_method") {
    return (
      {
        exact: "名称精确匹配",
        alias: "别名规则匹配",
        llm: "模型候选映射",
        unmatched: "暂未匹配",
      }[String(value)] ?? String(value)
    );
  }
  if (key === "change_type") {
    return (
      { added: "新增", removed: "删除", modified: "修改" }[String(value)] ??
      String(value)
    );
  }
  if (key === "proposed_level") {
    return (
      {
        required: "必备能力",
        preferred: "加分能力",
        out_of_scope: "不再纳入",
      }[String(value)] ?? String(value)
    );
  }
  if (typeof value === "object") return JSON.stringify(value);
  return String(value || "未提供");
}

function SystemOutputView({
  task,
  onAdopt,
}: {
  task: ReviewTask;
  onAdopt: (decision: ReviewDecision, rationale: string) => void;
}) {
  const output = task.system_output;
  const hidden = new Set([
    "title",
    "question",
    "prelabel",
    "last_decision",
    "last_rationale",
  ]);
  const fields = Object.entries(output).filter(
    ([key]) => !hidden.has(key) && FIELD_LABELS[key],
  );
  const prelabel = output.prelabel as
    | {
        suggested_decision: ReviewDecision;
        confidence: number;
        rationale: string;
      }
    | undefined;
  return (
    <>
      <dl className="tasks-system-output">
        {fields.map(([key, value]) => (
          <div key={key}>
            <dt>{FIELD_LABELS[key]}</dt>
            <dd>{outputValue(key, value)}</dd>
          </div>
        ))}
      </dl>
      {fields.length === 0 && !prelabel ? (
        <p className="tasks-system-empty">
          系统尚未返回可比较的结构化建议，请依据冻结样本完成判断。
        </p>
      ) : null}
      {prelabel ? (
        <div className="tasks-prelabel-summary">
          <div>
            <Tag color="gold">
              {DECISION_OPTIONS.find(
                (item) => item.value === prelabel.suggested_decision,
              )?.label ?? prelabel.suggested_decision}
            </Tag>
            <strong>{`AI 预审建议 · 置信度 ${Math.round(prelabel.confidence * 100)}%`}</strong>
          </div>
          <p>{prelabel.rationale}</p>
          <Button
            onClick={() =>
              onAdopt(prelabel.suggested_decision, prelabel.rationale)
            }
            size="small"
          >
            采用为当前判断
          </Button>
        </div>
      ) : null}
    </>
  );
}

export function TasksWorkbench({
  initialTasks,
  initialEvidence,
  initialView = "evidence",
  initialSource = "",
  evidenceFacets,
}: {
  initialTasks?: ReviewTask[];
  initialEvidence: EvidenceSearchResult;
  initialView?: "tasks" | "evidence";
  initialSource?: string;
  evidenceFacets: EvidenceFacets;
}) {
  const [tasks, setTasks] = useState<ReviewTask[]>(
    () => initialTasks ?? buildMockTasks(),
  );
  const [selectedId, setSelectedId] = useState<string | null>(
    () =>
      tasks.find((task) => task.status !== "RESOLVED")?.task_id ??
      tasks[0]?.task_id ??
      null,
  );
  const [decision, setDecision] = useState<ReviewDecision>("ACCEPT");
  const [rationale, setRationale] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [view, setView] = useState<"tasks" | "evidence">(initialView);
  const [taskFilter, setTaskFilter] = useState<"all" | "open" | "resolved">(
    () => (tasks.some((task) => task.status !== "RESOLVED") ? "open" : "all"),
  );

  const selected = useMemo(
    () => tasks.find((t) => t.task_id === selectedId) ?? null,
    [tasks, selectedId],
  );
  const filteredTasks = useMemo(
    () =>
      tasks.filter((task) => {
        if (taskFilter === "open") return task.status !== "RESOLVED";
        if (taskFilter === "resolved") return task.status === "RESOLVED";
        return true;
      }),
    [taskFilter, tasks],
  );

  function changeTaskFilter(next: "all" | "open" | "resolved") {
    setTaskFilter(next);
    const first = tasks.find((task) => {
      if (next === "open") return task.status !== "RESOLVED";
      if (next === "resolved") return task.status === "RESOLVED";
      return true;
    });
    setSelectedId(first?.task_id ?? null);
  }

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

  async function handleSubmit() {
    if (!selected || submitting) return;
    // mock 模式无后端，保持纯本地状态机；real 模式提交到标注 API
    if (isMockMode()) {
      transitionTo(selected.task_id, "SUBMITTED", { decision, rationale });
      setRationale("");
      return;
    }
    setSubmitting(true);
    try {
      await apiFetch(`/tasks/${selected.task_id}/decision`, {
        method: "POST",
        body: { decision, rationale },
      });
      transitionTo(selected.task_id, "SUBMITTED", { decision, rationale });
      setRationale("");
    } catch (error) {
      message.error(
        `提交失败：${error instanceof Error ? error.message : "网络异常"}`,
      );
    } finally {
      setSubmitting(false);
    }
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
        <div className="governance-toolbar">
          <div>
            <h1 className="sr-only">证据审核</h1>
            <strong>证据审核</strong>
            <span>查看证据事实并完成人工判断</span>
          </div>
          <Segmented
            aria-label="切换证据审核视图"
            onChange={(value) => setView(value as "tasks" | "evidence")}
            options={[
              { label: "证据库", value: "evidence" },
              { label: "审核任务", value: "tasks" },
            ]}
            value={view}
          />
        </div>
        {view === "evidence" ? (
          <EvidenceBrowser
            facets={evidenceFacets}
            initial={initialEvidence}
            initialSource={initialSource}
          />
        ) : (
          <section
            aria-label="审核任务"
            className="tasks-workbench"
            id="task-workspace"
          >
            <div className="tasks-layout">
              <aside aria-label="任务列表" className="tasks-list">
                <div className="tasks-list-heading">
                  <SectionHeader
                    meta={`${filteredTasks.length} / ${tasks.length} 条`}
                    title="审核任务"
                  />
                  <Select
                    aria-label="筛选任务状态"
                    onChange={(value) =>
                      changeTaskFilter(value as "all" | "open" | "resolved")
                    }
                    options={[
                      { label: "全部任务", value: "all" },
                      { label: "待处理", value: "open" },
                      { label: "已完成", value: "resolved" },
                    ]}
                    size="small"
                    value={taskFilter}
                  />
                </div>
                <ul>
                  {filteredTasks.map((t) => (
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
                          <Tag>{TASK_TYPE_LABELS[t.task_type]}</Tag>
                          <Tag color={REVIEW_STATUS_TONES[t.status]}>
                            {STATUS_LABEL[t.status]}
                          </Tag>
                          {t.priority === "high" && t.status !== "RESOLVED" ? (
                            <Tag color={REVIEW_PRIORITY_TONES.high}>
                              高优先级
                            </Tag>
                          ) : null}
                          {t.needs_dual_review ? (
                            <Tag color="purple">需双审</Tag>
                          ) : null}
                        </div>
                        <strong>{taskSubject(t)}</strong>
                        <small>{taskQuestion(t)}</small>
                      </button>
                    </li>
                  ))}
                </ul>
              </aside>

              <section aria-label="审核工作区" className="tasks-workspace">
                {selected ? (
                  <>
                    <div className="tasks-workspace-header">
                      <Tag color={REVIEW_STATUS_TONES[selected.status]}>
                        {STATUS_LABEL[selected.status]}
                      </Tag>
                      <Tag>{TASK_TYPE_LABELS[selected.task_type]}</Tag>
                      {selected.needs_dual_review ? (
                        <Tag color="purple">需双审</Tag>
                      ) : null}
                    </div>
                    <h2 className="tasks-subject">{taskSubject(selected)}</h2>

                    <section className="tasks-question" aria-label="待判断内容">
                      <span>需判断</span>
                      <strong>{taskQuestion(selected)}</strong>
                      {selected.needs_dual_review ? (
                        <p>
                          该任务需要两位审核者独立判断，出现分歧后进入复核。
                        </p>
                      ) : null}
                    </section>

                    <section
                      aria-label="系统建议"
                      className="tasks-workspace-section"
                    >
                      <SectionHeader title="系统建议" />
                      <SystemOutputView
                        onAdopt={(nextDecision, nextRationale) => {
                          setDecision(nextDecision);
                          setRationale(nextRationale);
                        }}
                        task={selected}
                      />
                    </section>

                    <section
                      aria-label="证据"
                      className="tasks-workspace-section"
                    >
                      <SectionHeader
                        meta={`${selected.evidence_ids.length} 条`}
                        title="判断依据"
                      />
                      <div className="tasks-evidence-summary">
                        <p>
                          {selected.evidence_ids.length
                            ? `该判断关联 ${selected.evidence_ids.length} 条来源证据。`
                            : "该任务来自冻结评测样本，以样本内容和人工标准作为判断依据。"}
                        </p>
                        {selected.evidence_ids.length ? (
                          <Button onClick={() => setView("evidence")}>
                            打开证据库核对
                          </Button>
                        ) : null}
                      </div>
                    </section>

                    {selected.status === "RESOLVED" ? (
                      <section
                        aria-label="审核结果"
                        className="tasks-workspace-section tasks-review-result"
                      >
                        <SectionHeader title="审核结果" />
                        <div>
                          <Tag color="green">
                            {DECISION_OPTIONS.find(
                              (item) =>
                                item.value ===
                                selected.system_output.last_decision,
                            )?.label ?? "已完成"}
                          </Tag>
                          <p>
                            {String(
                              selected.system_output.last_rationale ??
                                "该任务已经完成人工判断。",
                            )}
                          </p>
                        </div>
                      </section>
                    ) : (
                      <section
                        aria-label="人工决策"
                        className="tasks-workspace-section"
                      >
                        <SectionHeader title="做出判断" />
                        <div className="tasks-decision">
                          <Select
                            aria-label="选择审核结论"
                            onChange={(v) => setDecision(v as ReviewDecision)}
                            options={DECISION_OPTIONS}
                            style={{ minWidth: 160 }}
                            value={decision}
                          />
                          <Input
                            aria-label="决策理由"
                            onChange={(e) => setRationale(e.target.value)}
                            placeholder="说明接受、修改或拒绝的理由"
                            value={rationale}
                          />
                        </div>
                      </section>
                    )}

                    <details className="tasks-technical-details">
                      <summary>运行与数据详情</summary>
                      <dl>
                        <div>
                          <dt>任务 ID</dt>
                          <dd>{selected.task_id}</dd>
                        </div>
                        <div>
                          <dt>来源记录</dt>
                          <dd>{selected.source_record_id || "未登记"}</dd>
                        </div>
                        <div>
                          <dt>运行版本</dt>
                          <dd>{selected.run_id}</dd>
                        </div>
                        <div>
                          <dt>数据集版本</dt>
                          <dd>{selected.dataset_version}</dd>
                        </div>
                      </dl>
                    </details>

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
                          disabled={submitting}
                          icon={<CheckCircle aria-hidden size={15} />}
                          loading={submitting}
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
                      {selected.status !== "RESOLVED" ? (
                        <span className="tasks-workspace-state-meta">
                          {`当前状态：${STATUS_LABEL[selected.status]}`}
                        </span>
                      ) : null}
                    </div>
                  </>
                ) : (
                  <Empty description="暂无任务，请先领取。" />
                )}
              </section>
            </div>
          </section>
        )}
      </div>
    </AppShell>
  );
}

export { XCircle as _XCircle, ArrowSquareOut as _ArrowSquareOut };
