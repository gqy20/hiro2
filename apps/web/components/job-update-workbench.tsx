"use client";

import { useMemo, useState } from "react";
import {
  CheckCircle,
  FileText,
  FunnelSimple,
  MagnifyingGlass,
  PaperPlaneTilt,
  XCircle,
} from "@phosphor-icons/react";
import { Button, Modal, Select, Skeleton, Tag, Tooltip } from "antd";

import { AppShell } from "@/components/app-shell";
import { EvidenceDrawer } from "@/components/evidence-drawer";
import { ReviewProgress } from "@/components/review-progress";
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

const filterOptions: Array<"全部" | ChangeKind> = [
  "全部",
  "added",
  "removed",
  "modified",
];

const reviewLabels: Record<ReviewStatus, string> = {
  accepted: "已接受",
  needs_evidence: "待确认",
  rejected: "已拒绝",
  reviewing: "待审",
};

type JobUpdateWorkbenchProps = { fixture: JobUpdateFixture };

export function JobUpdateWorkbench({ fixture }: JobUpdateWorkbenchProps) {
  const [items, setItems] = useState(fixture.changes);
  const [selected, setSelected] = useState<ChangeItem | null>(null);
  const [running, setRunning] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [published, setPublished] = useState(false);
  const [filter, setFilter] = useState<"全部" | ChangeKind>("全部");

  const pending = items.filter(
    (item) => item.status === "reviewing" || item.status === "needs_evidence",
  ).length;
  const reviewCounts = {
    accepted: items.filter((item) => item.status === "accepted").length,
    needsEvidence: items.filter((item) => item.status === "needs_evidence")
      .length,
    reviewing: items.filter((item) => item.status === "reviewing").length,
  };
  const visibleItems = useMemo(
    () =>
      filter === "全部" ? items : items.filter((item) => item.kind === filter),
    [filter, items],
  );

  function updateStatus(id: string, status: ReviewStatus) {
    setItems((current) =>
      current.map((item) => (item.id === id ? { ...item, status } : item)),
    );
  }

  function runAnalysis() {
    if (running) return;
    setRunning(true);
    window.setTimeout(() => {
      setItems(fixture.changes);
      setRunning(false);
    }, 1400);
  }

  function publish() {
    setPublishing(false);
    setPublished(true);
  }

  return (
    <AppShell>
      <div className="workbench">
        <section className="context-panel" aria-labelledby="page-title">
          <div className="page-heading">
            <div className="title-with-meta">
              <h1 id="page-title">岗位更新</h1>
              <span className="page-meta">{`${fixture.context.baselineVersion} → ${fixture.context.targetVersion}`}</span>
            </div>
            <div className="header-tags">
              <Tag>演示数据</Tag>
              <Tag color={published ? "green" : "gold"}>
                {published
                  ? `已发布 ${fixture.context.targetVersion}`
                  : `草稿 ${fixture.context.targetVersion}`}
              </Tag>
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
              <Select
                defaultValue={fixture.context.timeWindow}
                options={[{ value: fixture.context.timeWindow }]}
              />
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
              <div>
                <dt>待审变化</dt>
                <dd>{pending}</dd>
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
            <div className="toolbar-actions">
              <div className="filter-tabs" role="tablist" aria-label="变化类型">
                {filterOptions.map((value) => (
                  <button
                    aria-selected={filter === value}
                    className={
                      filter === value
                        ? "filter-tab filter-tab-active"
                        : "filter-tab"
                    }
                    key={value}
                    onClick={() => setFilter(value)}
                    role="tab"
                    type="button"
                  >
                    {value === "全部" ? "全部" : labels[value]}
                  </button>
                ))}
              </div>
              <Tooltip title="筛选高置信变化">
                <Button
                  aria-label="筛选高置信变化"
                  icon={<FunnelSimple size={17} />}
                  size="small"
                  type="text"
                />
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
                          />
                        ))}
                    </div>
                  </section>
                ),
              )}
            </div>
          )}

          <footer className="diff-footer">
            <span>
              {pending === 0
                ? "审核完成，可发布新版本"
                : `还有 ${pending} 条变化待处理`}
            </span>
            <Button
              disabled={pending > 0 || published}
              icon={<PaperPlaneTilt />}
              loading={publishing}
              onClick={() => setPublishing(true)}
              type="primary"
            >
              {published ? "已发布" : "发布版本"}
            </Button>
          </footer>
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

      <EvidenceDrawer
        context={fixture.context}
        item={selected}
        onClose={() => setSelected(null)}
      />
      <Modal
        cancelText="继续审核"
        centered
        okButtonProps={{ disabled: pending > 0 }}
        okText={`发布 ${fixture.context.targetVersion}`}
        onCancel={() => setPublishing(false)}
        onOk={publish}
        open={publishing}
        title="发布岗位版本"
      >
        <p>
          {pending === 0
            ? `发布后将创建不可变的 ${fixture.context.jobTitle} ${fixture.context.targetVersion}。`
            : "请先完成所有审核项。"}
        </p>
      </Modal>
    </AppShell>
  );
}

type ChangeRowProps = {
  item: ChangeItem;
  onAccept: () => void;
  onEvidence: () => void;
  onReject: () => void;
};

function ChangeRow({ item, onAccept, onEvidence, onReject }: ChangeRowProps) {
  const isReviewing =
    item.status === "reviewing" || item.status === "needs_evidence";
  const confidence = Math.round(item.confidence * 100);

  return (
    <article className="change-row">
      <div className="change-row-topline">
        <h4>{item.title}</h4>
        <StatusMark status={item.status} />
      </div>
      <p>{item.detail}</p>
      <div className="change-metrics">
        <span
          className={
            item.confidence < 0.8
              ? "confidence-meter confidence-meter-caution"
              : "confidence-meter"
          }
          aria-label={`${confidence}% 置信`}
        >
          <b>{`${confidence}%`}</b>
          <i aria-hidden>
            <u style={{ width: `${confidence}%` }} />
          </i>
          <em>置信</em>
        </span>
        <button
          onClick={onEvidence}
          type="button"
        >{`${item.evidence.length} 条证据`}</button>
        {isReviewing ? (
          <span className="review-actions" aria-label="审核动作">
            <Tooltip title="接受变化">
              <Button
                aria-label={`接受 ${item.title}`}
                className="review-action review-action-accept"
                icon={<CheckCircle size={16} />}
                onClick={onAccept}
                size="small"
                type="text"
              />
            </Tooltip>
            <Tooltip title="拒绝变化">
              <Button
                aria-label={`拒绝 ${item.title}`}
                className="review-action review-action-reject"
                icon={<XCircle size={16} />}
                onClick={onReject}
                size="small"
                type="text"
              />
            </Tooltip>
          </span>
        ) : null}
      </div>
    </article>
  );
}

function StatusMark({ status }: { status: ReviewStatus }) {
  const icon =
    status === "accepted" ? (
      <CheckCircle aria-hidden weight="fill" />
    ) : status === "rejected" ? (
      <XCircle aria-hidden weight="fill" />
    ) : (
      <i aria-hidden />
    );
  return (
    <span className={`status-mark status-mark-${status}`}>
      {icon}
      <span>{reviewLabels[status]}</span>
    </span>
  );
}
