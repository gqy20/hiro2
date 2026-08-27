"use client";

import Link from "next/link";
import { useState } from "react";
import {
  CheckCircle,
  FileText,
  MagnifyingGlass,
  PaperPlaneTilt,
  Warning,
} from "@phosphor-icons/react";
import { Alert, Button, Modal, Select, Skeleton, Tag, Tooltip } from "antd";

import { AppShell } from "@/components/app-shell";
import { EvidenceDrawer } from "@/components/evidence-drawer";
import { PublishResultView } from "@/components/publish-result";
import { ReviewProgress } from "@/components/review-progress";
import {
  ConfidenceMeter,
  ReviewActions,
  StatusMark,
} from "@/components/review-ui";
import { FixtureState } from "@/components/workflow-ui";
import { WorkflowContext } from "@/components/workflow-context";
import { publishJobVersion, type PublishResult } from "@/lib/api/queries";
import {
  type ChangeItem,
  type ChangeKind,
  type JobUpdateFixture,
  type ReviewStatus,
} from "@/lib/job-update";

const labels: Record<ChangeKind, string> = {
  added: "新增",
  modified: "修改",
  removed: "删除",
};

function splitWindow(value: string): { label: string; start: string; end: string }[] {
  return value.split(" vs ").map((part, index) => {
    const [start = "", end = ""] = part.split(":");
    return { label: index === 0 ? "基准窗" : "观察窗", start, end };
  });
}

type JobUpdateWorkbenchProps = {
  fixture: JobUpdateFixture;
  state?: "ready" | "empty" | "error";
};

export function JobUpdateWorkbench({
  fixture,
  state = "ready",
}: JobUpdateWorkbenchProps) {
  const windows = splitWindow(fixture.context.timeWindow);
  const [items, setItems] = useState(fixture.changes);
  const [selected, setSelected] = useState<ChangeItem | null>(null);
  const [running, setRunning] = useState(false);
  const [publishModalOpen, setPublishModalOpen] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [publishedResult, setPublishedResult] = useState<PublishResult | null>(
    null,
  );
  const [publishError, setPublishError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftDetail, setDraftDetail] = useState("");

  const pending = items.filter(
    (item) => item.status === "reviewing" || item.status === "needs_evidence",
  ).length;
  const reviewCounts = {
    accepted: items.filter((item) => item.status === "accepted").length,
    rejected: items.filter((item) => item.status === "rejected").length,
    needsEvidence: items.filter((item) => item.status === "needs_evidence")
      .length,
    reviewing: items.filter((item) => item.status === "reviewing").length,
  };
  const visibleItems = items;

  function updateStatus(id: string, status: ReviewStatus) {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, status } : item)),
    );
  }

  function startEditing(item: ChangeItem) {
    setEditingId(item.id);
    setDraftDetail(item.detail);
  }

  function saveDetail(id: string) {
    setItems((current) =>
      current.map((item) =>
        item.id === id ? { ...item, detail: draftDetail } : item,
      ),
    );
    setEditingId(null);
  }

  function runAnalysis() {
    if (running) return;
    setRunning(true);
    window.setTimeout(() => {
      setItems(fixture.changes);
      setRunning(false);
    }, 1400);
  }

  async function publish() {
    setPublishing(true);
    setPublishError(null);
    try {
      const result = await publishJobVersion(
        "default",
        fixture.context.targetVersion,
      );
      setPublishedResult(result);
      setPublishModalOpen(false);
      setPublishing(false);
    } catch (err) {
      setPublishError(
        err instanceof Error ? err.message : "发布失败，请稍后重试。",
      );
      setPublishing(false);
    }
  }

  // 早返回必须在所有 hooks 调用之后（React Rules of Hooks）。
  if (state === "error")
    return (
      <AppShell>
        <FixtureState
          errorText="岗位版本数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  if (state === "empty")
    return (
      <AppShell>
        <FixtureState
          action={<Link href="/"><Button type="primary">返回工作台</Button></Link>}
          emptyText="当前版本暂未检测到能力变化。"
          state="empty"
        />
      </AppShell>
    );
  if (publishedResult)
    return (
      <PublishResultView
        jobTitle={fixture.context.jobTitle}
        onBack={() => setPublishedResult(null)}
        publishedAt={publishedResult.publishedAt}
        versionId={publishedResult.versionId}
        reviewCounts={{
          accepted: reviewCounts.accepted,
          rejected: reviewCounts.rejected,
          pending: reviewCounts.reviewing + reviewCounts.needsEvidence,
        }}
        targetVersion={fixture.context.targetVersion}
      />
    );

  return (
    <AppShell>
      <div className="workflow-page">
        <WorkflowContext eyebrow="岗位版本" title={fixture.context.jobTitle} stage="审核能力变化" next="完成审核后发布新版本" />
      <div className="workbench">
        <section className="context-panel" aria-labelledby="page-title">
          <div className="page-heading">
            <div className="title-with-meta">
              <h1 id="page-title">岗位更新</h1>
            </div>
            <div className="header-tags">
              <Tag color="gold">{`草稿 ${fixture.context.targetVersion}`}</Tag>
            </div>
          </div>

          <div className="context-form">
            <label>
              岗位
              <Select
                defaultValue={fixture.context.jobTitle}
                options={[{ value: fixture.context.jobTitle }]}
              />
            </label>
            <label>
              基准版本
              <Select
                defaultValue={fixture.context.baselineVersion}
                options={[{ value: fixture.context.baselineVersion }]}
              />
            </label>
            <label>
              观察窗口
              <div className="context-window" role="group" aria-label="观察窗口">
                {windows.map((window) => (
                  <div className="context-window-row" key={window.label}>
                    <span>{window.label}</span>
                    <strong>{window.start}</strong>
                    <i>至</i>
                    <strong>{window.end}</strong>
                  </div>
                ))}
              </div>
            </label>
          </div>

          <div className="context-summary">
            <div>
              <span>有效样本</span>
              <strong>{fixture.summary.validSamples}</strong>
            </div>
            <div>
              <span>覆盖企业</span>
              <strong>{fixture.summary.companies}</strong>
            </div>
            <div>
              <span>证据来源</span>
              <strong>{fixture.summary.evidenceSources}</strong>
            </div>
          </div>

          <Button
            block
            icon={<MagnifyingGlass />}
            loading={running}
            onClick={runAnalysis}
            type="primary"
          >
            {running ? "分析中" : "分析变化"}
          </Button>

          <section className="version-summary" aria-labelledby="version-title">
            <div className="section-heading compact-heading">
              <div className="inline-heading">
                <h2 id="version-title">版本对比</h2>
              </div>
              <Tooltip title="查看版本说明">
                <Button
                  aria-label="查看版本说明"
                  icon={<FileText size={17} />}
                  size="small"
                  type="text"
                />
              </Tooltip>
            </div>
            <dl>
              <div>
                <dt>必备技能</dt>
                <dd>
                  <span>7 → 8</span>
                  <strong className="delta delta-added">+1</strong>
                </dd>
              </div>
              <div>
                <dt>加分技能</dt>
                <dd>
                  <span>5 → 4</span>
                  <strong className="delta delta-removed">-1</strong>
                </dd>
              </div>
            </dl>
          </section>
        </section>

        <section className="diff-panel" aria-labelledby="diff-title">
          <div className="diff-toolbar">
            <div className="inline-heading">
              <h2 id="diff-title">能力变化</h2>
              <span>{`${visibleItems.length} 条结果`}</span>
            </div>
            <div className="diff-toolbar-actions">
              <span className="diff-toolbar-status">按变化类型分组</span>
              <Tooltip title={pending > 0 ? "请先完成右侧审核队列中的全部变化" : undefined}>
                <span>
                  <Button
                    disabled={pending > 0}
                    icon={<PaperPlaneTilt />}
                    onClick={() => {
                      setPublishError(null);
                      setPublishModalOpen(true);
                    }}
                    size="small"
                    type="primary"
                  >
                    发布版本
                  </Button>
                </span>
              </Tooltip>
            </div>
          </div>

          {running ? (
            <div className="diff-skeleton" aria-label="正在生成岗位变化">
              <Skeleton active paragraph={{ rows: 12 }} title={false} />
            </div>
          ) : (
            <div className="change-grid">
              {(["added", "removed", "modified"] as ChangeKind[]).map(
                (kind) => (
                  <section
                    className={`change-column change-${kind}`}
                    key={kind}
                    aria-labelledby={`${kind}-title`}
                  >
                    <div className="change-column-heading">
                      <h3 id={`${kind}-title`}>{labels[kind]}</h3>
                      <span>
                        {
                          visibleItems.filter((item) => item.kind === kind)
                            .length
                        }
                      </span>
                    </div>
                    <div className="change-list">
                      {visibleItems
                        .filter((item) => item.kind === kind)
                        .map((item) => (
                          <ChangeRow
                            item={item}
                            key={item.id}
                            onAccept={() => updateStatus(item.id, "accepted")}
                            onEvidence={() => setSelected(item)}
                            onReject={() => updateStatus(item.id, "rejected")}
                            editing={editingId === item.id}
                            onEdit={() => startEditing(item)}
                            onCancelEdit={() => setEditingId(null)}
                            onSaveEdit={() => saveDetail(item.id)}
                            draftDetail={draftDetail}
                            onDraftDetailChange={setDraftDetail}
                          />
                        ))}
                    </div>
                  </section>
                ),
              )}
            </div>
          )}

          {items.length > 0 ? (
            <section
              className="downstream-impact"
              aria-labelledby="impact-title"
            >
              <h3 id="impact-title">下游影响</h3>
              <span className="downstream-impact-copy">这些变化会同步影响技能图谱与人岗诊断</span>
              <Link className="impact-link" href="/skills">
                查看技能图谱 →
              </Link>
            </section>
          ) : null}

        </section>

        <aside className="evidence-panel" aria-label="审核和证据">
          <ReviewProgress
            runId={fixture.run.id}
            running={running}
            steps={fixture.progressSteps}
          />
          <div className="review-distribution" aria-label="审核构成">
            <span className="distribution-accepted">
              <i aria-hidden />
              <b>{reviewCounts.accepted}</b>
              <small>已接受</small>
            </span>
            <span className="distribution-reviewing">
              <i aria-hidden />
              <b>{reviewCounts.reviewing}</b>
              <small>待审</small>
            </span>
            <span className="distribution-evidence">
              <i aria-hidden />
              <b>{reviewCounts.needsEvidence}</b>
              <small>待确认</small>
            </span>
          </div>
          <section className="review-queue" aria-labelledby="queue-title">
            <div className="section-heading">
              <div className="inline-heading">
                <h2 id="queue-title">审核队列</h2>
                <span>{`${pending} 条待处理`}</span>
              </div>
            </div>
            {items.map((item) => (
              <button
                className="queue-item"
                key={item.id}
                onClick={() => setSelected(item)}
                type="button"
              >
                <span>{item.title}</span>
                <StatusMark status={item.status} />
              </button>
            ))}
          </section>
          <div className="review-note">
            <CheckCircle aria-hidden size={18} weight="fill" />
            <span>{`已接受的变化将进入 ${fixture.context.targetVersion} 草稿，发布后不可覆盖历史版本。`}</span>
          </div>
        </aside>
      </div>
      </div>

      <EvidenceDrawer
        context={fixture.context}
        item={selected}
        onClose={() => setSelected(null)}
      />
      <Modal
        cancelText="继续审核"
        centered
        confirmLoading={publishing}
        okButtonProps={{ disabled: pending > 0 }}
        okText={`发布 ${fixture.context.targetVersion}`}
        onCancel={() => {
          if (!publishing) setPublishModalOpen(false);
        }}
        onOk={publish}
        open={publishModalOpen}
        title="发布岗位版本"
      >
        {publishError ? (
          <Alert
            description={publishError}
            icon={<Warning aria-hidden />}
            showIcon
            type="error"
          />
        ) : (
          <p>
            {pending === 0
              ? `发布后将创建不可变的 ${fixture.context.jobTitle} ${fixture.context.targetVersion}。`
              : "请先完成所有审核项。"}
          </p>
        )}
      </Modal>
    </AppShell>
  );
}

type ChangeRowProps = {
  item: ChangeItem;
  onAccept: () => void;
  onEvidence: () => void;
  onReject: () => void;
  editing: boolean;
  onEdit: () => void;
  onCancelEdit: () => void;
  onSaveEdit: () => void;
  draftDetail: string;
  onDraftDetailChange: (value: string) => void;
};

function ChangeRow({
  item,
  onAccept,
  onEvidence,
  onReject,
  editing,
  onEdit,
  onCancelEdit,
  onSaveEdit,
  draftDetail,
  onDraftDetailChange,
}: ChangeRowProps) {
  const isReviewing =
    item.status === "reviewing" || item.status === "needs_evidence";
  return (
    <article className="change-row">
      <div className="change-row-topline">
        <h4>{item.title}</h4>
        <StatusMark status={item.status} />
      </div>
      {editing ? (
        <div className="inline-edit">
          <textarea
            aria-label={`编辑 ${item.title}`}
            onChange={(event) => onDraftDetailChange(event.target.value)}
            value={draftDetail}
          />
          <span>
            <Button onClick={onCancelEdit} size="small">
              取消
            </Button>
            <Button onClick={onSaveEdit} size="small" type="primary">
              保存
            </Button>
          </span>
        </div>
      ) : (
        <p>{item.detail}</p>
      )}
      <div className="change-metrics">
        <ConfidenceMeter confidence={item.confidence} />
        <button
          onClick={onEvidence}
          type="button"
        >{`${item.evidence.length} 条证据`}</button>
        {isReviewing ? (
          <>
            <Button
              aria-label={`编辑说明 ${item.title}`}
              className="review-edit"
              onClick={onEdit}
              size="small"
              type="text"
            >
              编辑
            </Button>
            <ReviewActions
              label={item.title}
              onAccept={onAccept}
              onReject={onReject}
            />
          </>
        ) : null}
      </div>
    </article>
  );
}
