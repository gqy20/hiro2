"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowSquareOut, PencilSimple } from "@phosphor-icons/react";
import { Button, Input, Modal, Select, Tag, message } from "antd";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/workflow-ui";
import { TemporalNav } from "@/components/temporal-nav";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type {
  JobImpactChangeType,
  JobImpactReviewStatus,
  JobImpactSuggestion,
} from "@/lib/temporal";

const CHANGE_LABEL: Record<JobImpactChangeType, string> = {
  add: "新增",
  remove: "移除",
  modify: "修改",
  promote: "升级",
  demote: "降级",
};

const CHANGE_TONE: Record<JobImpactChangeType, string> = {
  add: "green",
  remove: "red",
  modify: "blue",
  promote: "gold",
  demote: "orange",
};

const STATUS_TONE: Record<JobImpactReviewStatus, string> = {
  PENDING: "default",
  ACCEPTED: "green",
  MODIFIED: "blue",
  REJECTED: "red",
};

const LEVEL_OPTIONS = [
  { label: "required（必备）", value: "required" },
  { label: "preferred（加分）", value: "preferred" },
  { label: "out_of_scope（不在范围）", value: "out_of_scope" },
];

export function TemporalSuggestionsWorkbench({
  initial,
}: {
  initial: JobImpactSuggestion[];
}) {
  const [items, setItems] = useState(initial);
  const [editing, setEditing] = useState<JobImpactSuggestion | null>(null);
  const [newLevel, setNewLevel] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);

  // 审核动作持久化到后端审核日志；mock 模式保持纯本地状态
  async function submitReview(
    id: string,
    decision: "accepted" | "rejected" | "modified",
    suggestedLevel?: string,
  ): Promise<boolean> {
    if (isMockMode()) return true;
    setSubmitting(true);
    try {
      await apiFetch(`/temporal/suggestions/${id}/review`, {
        method: "POST",
        body: {
          decision,
          note: "Web 影响建议审核",
          ...(suggestedLevel ? { suggested_level: suggestedLevel } : {}),
        },
      });
      return true;
    } catch (error) {
      message.error(
        `审核提交失败：${error instanceof Error ? error.message : "网络异常"}`,
      );
      return false;
    } finally {
      setSubmitting(false);
    }
  }

  async function accept(id: string) {
    if (!(await submitReview(id, "accepted"))) return;
    setItems((current) =>
      current.map((s) =>
        s.suggestion_id === id
          ? { ...s, review_status: "ACCEPTED" as const }
          : s,
      ),
    );
  }
  async function reject(id: string) {
    if (!(await submitReview(id, "rejected"))) return;
    setItems((current) =>
      current.map((s) =>
        s.suggestion_id === id
          ? { ...s, review_status: "REJECTED" as const }
          : s,
      ),
    );
  }
  function startModify(s: JobImpactSuggestion) {
    setEditing(s);
    setNewLevel(s.suggested_level);
  }
  async function saveModify() {
    if (!editing) return;
    if (!(await submitReview(editing.suggestion_id, "modified", newLevel)))
      return;
    setItems((current) =>
      current.map((s) =>
        s.suggestion_id === editing.suggestion_id
          ? {
              ...s,
              suggested_level: newLevel,
              review_status: "MODIFIED" as const,
            }
          : s,
      ),
    );
    setEditing(null);
  }

  const pending = items.filter((s) => s.review_status === "PENDING");

  return (
    <AppShell>
      <section
        className="temporal-workbench"
        aria-labelledby="suggestions-title"
      >
        <header className="page-heading">
          <h1 id="suggestions-title">影响建议（JobImpactSuggestion）</h1>
          <p>
            {`${pending.length} 条待审 · 来自 ForecastEngine，可进入岗位审核`}
          </p>
        </header>
        <TemporalNav />

        <SectionHeader
          action={
            <Button
              href="/jobs"
              icon={<ArrowSquareOut aria-hidden size={15} />}
              type="primary"
            >
              跳转岗位审核
            </Button>
          }
          meta={`${items.length} 条`}
          title="建议列表"
        />
        <ul className="temporal-suggestion-list">
          {items.map((s) => (
            <li
              className={`temporal-suggestion-item status-${s.review_status.toLowerCase()}`}
              key={s.suggestion_id}
            >
              <div className="temporal-suggestion-meta">
                <Tag color={CHANGE_TONE[s.change_type]}>
                  {CHANGE_LABEL[s.change_type]}
                </Tag>
                <strong>{s.skill_id}</strong>
                <Tag color={STATUS_TONE[s.review_status]}>
                  {s.review_status}
                </Tag>
              </div>
              <p className="temporal-suggestion-reason">{s.reason}</p>
              <div className="temporal-suggestion-detail">
                <span>
                  {`job_id ${s.job_id} · 建议层级 ${s.suggested_level}`}
                </span>
                <span>{`${s.evidence_ids.length} 条证据`}</span>
              </div>
              {s.review_status === "PENDING" ? (
                <div className="temporal-suggestion-actions">
                  <Button
                    disabled={submitting}
                    onClick={() => accept(s.suggestion_id)}
                    size="small"
                    type="primary"
                  >
                    接受
                  </Button>
                  <Button
                    disabled={submitting}
                    icon={<PencilSimple size={14} />}
                    onClick={() => startModify(s)}
                    size="small"
                  >
                    修改
                  </Button>
                  <Button
                    danger
                    disabled={submitting}
                    onClick={() => reject(s.suggestion_id)}
                    size="small"
                  >
                    拒绝
                  </Button>
                </div>
              ) : null}
              {s.review_status === "ACCEPTED" ||
              s.review_status === "MODIFIED" ? (
                <div className="temporal-suggestion-actions">
                  <Link
                    className="temporal-suggestion-goto"
                    href="/jobs"
                    aria-label={`前往岗位更新流程处理 ${s.skill_id}`}
                  >
                    前往岗位更新流程 <ArrowSquareOut aria-hidden size={14} />
                  </Link>
                </div>
              ) : null}
            </li>
          ))}
        </ul>
      </section>

      <Modal
        cancelText="取消"
        okText="保存修改"
        onCancel={() => setEditing(null)}
        onOk={saveModify}
        open={editing !== null}
        title={`修改 ${editing?.skill_id ?? ""} 的建议层级`}
      >
        <Input
          aria-label="建议层级文本"
          onChange={(e) => setNewLevel(e.target.value)}
          value={newLevel}
        />
        <Select
          aria-label="建议层级"
          onChange={(v) => setNewLevel(String(v))}
          options={LEVEL_OPTIONS}
          style={{ marginTop: 12, width: "100%" }}
          value={newLevel}
        />
      </Modal>
    </AppShell>
  );
}
