"use client";

import { useState } from "react";
import {
  ArrowSquareOut,
  CheckCircle,
  WarningCircle,
} from "@phosphor-icons/react";
import { Button, Descriptions, Drawer, Grid, Modal, Tag } from "antd";

import { formatDate } from "@/lib/time";
import type { ChangeItem, Evidence, JobUpdateContext } from "@/lib/job-update";

type EvidenceDrawerProps = {
  context: JobUpdateContext;
  item: ChangeItem | null;
  onClose: () => void;
};

export function EvidenceDrawer({
  context,
  item,
  onClose,
}: EvidenceDrawerProps) {
  const screens = Grid.useBreakpoint();
  const desktop = Boolean(screens.md);
  const [selectedEvidence, setSelectedEvidence] = useState<Evidence | null>(
    null,
  );

  function closeDrawer() {
    setSelectedEvidence(null);
    onClose();
  }

  return (
    <Drawer
      className="evidence-drawer"
      closeIcon={null}
      onClose={closeDrawer}
      open={item !== null}
      placement={desktop ? "right" : "bottom"}
      size="large"
      title={item ? `${item.title}的依据` : "依据"}
      extra={
        item ? (
          <Tag
            color={item.confidence >= 0.8 ? "green" : "gold"}
          >{`${Math.round(item.confidence * 100)}% 置信`}</Tag>
        ) : null
      }
    >
      {item ? (
        <div className="drawer-content">
          <section className="drawer-summary" aria-label="变化说明">
            <p>{item.detail}</p>
          </section>

          <Descriptions bordered column={1} size="small" title="审核上下文">
            <Descriptions.Item label="基准版本">
              {`${context.jobTitle} ${context.baselineVersion}`}
            </Descriptions.Item>
            <Descriptions.Item label="目标草稿">{`${context.targetVersion} 草稿`}</Descriptions.Item>
            <Descriptions.Item label="观察窗口">
              {context.timeWindow}
            </Descriptions.Item>
          </Descriptions>

          <section className="evidence-list" aria-label="证据片段">
            <h2>原文片段</h2>
            {item.evidence.map((evidence) => {
              const Icon =
                evidence.stance === "支持" ? CheckCircle : WarningCircle;
              return (
                <article className="evidence-item" key={evidence.id}>
                  <div className="evidence-heading">
                    <span
                      className={
                        evidence.stance === "支持"
                          ? "stance stance-support"
                          : "stance stance-counter"
                      }
                    >
                      <Icon aria-hidden size={16} weight="fill" />
                      {evidence.stance}
                    </span>
                    <Tag>{evidence.sourceType}</Tag>
                  </div>
                  <p>“{evidence.excerpt}”</p>
                  <dl>
                    <div>
                      <dt>来源</dt>
                      <dd>{evidence.source}</dd>
                    </div>
                    <div>
                      <dt>发布</dt>
                      <dd>
                        {formatDate(evidence.publishedAt) ||
                          evidence.publishedAt}
                      </dd>
                    </div>
                    <div>
                      <dt>采集</dt>
                      <dd>
                        {formatDate(evidence.collectedAt) ||
                          evidence.collectedAt}
                      </dd>
                    </div>
                    <div>
                      <dt>质量</dt>
                      <dd>{evidence.quality.toFixed(2)}</dd>
                    </div>
                  </dl>
                  <div className="evidence-id">{evidence.id}</div>
                  <div className="evidence-actions">
                    {evidence.fullText ? (
                      <Button
                        onClick={() => setSelectedEvidence(evidence)}
                        size="small"
                        type="link"
                      >
                        查看原文
                      </Button>
                    ) : null}
                    {evidence.sourceUrl ? (
                      <Button
                        href={evidence.sourceUrl}
                        icon={<ArrowSquareOut />}
                        size="small"
                        target="_blank"
                        type="link"
                      >
                        打开来源
                      </Button>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </section>
        </div>
      ) : null}
      <Modal
        footer={null}
        onCancel={() => setSelectedEvidence(null)}
        open={selectedEvidence !== null}
        title={selectedEvidence ? `${selectedEvidence.source}原文` : "原文"}
      >
        {selectedEvidence ? (
          <p className="full-evidence">{selectedEvidence.fullText}</p>
        ) : null}
      </Modal>
    </Drawer>
  );
}
