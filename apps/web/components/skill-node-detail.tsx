"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowSquareOut } from "@phosphor-icons/react";
import { Button, Tag } from "antd";

import type { SkillNode } from "@/lib/skill";

const roleLabels: Record<SkillNode["role"], string> = {
  required: "必备",
  preferred: "加分",
};

const statusLabels: Record<SkillNode["status"], string> = {
  added: "新增",
  removed: "删除",
  modified: "修改",
  stable: "稳定",
};

const statusTone: Record<SkillNode["status"], string> = {
  added: "gold",
  removed: "red",
  modified: "blue",
  stable: "default",
};

const MAX_ALIASES = 12;
const MAX_JOB_REFS = 6;

export function SkillNodeDetail({
  node,
  allNodes,
  onOpenEvidence,
  onSelectNode,
}: {
  node: SkillNode;
  allNodes: SkillNode[];
  onOpenEvidence: () => void;
  onSelectNode: (id: string) => void;
}) {
  const isPoint = node.pointName !== null;
  const parentCapability = isPoint
    ? allNodes.find(
        (n) => n.capabilityId === node.capabilityId && n.pointName === null,
      )
    : null;
  const siblingPoints = isPoint
    ? allNodes.filter(
        (n) =>
          n.capabilityId === node.capabilityId &&
          n.pointName !== null &&
          n.id !== node.id,
      )
    : allNodes.filter(
        (n) => n.capabilityId === node.capabilityId && n.pointName !== null,
      );
  const aliases = node.aliases.slice(0, MAX_ALIASES);
  const aliasOverflow = node.aliases.length - aliases.length;
  const jobVersions = node.jobVersions ?? [];
  const signal = node.signal ?? null;
  const [showAllVersions, setShowAllVersions] = useState(false);
  const visibleJobVersions = showAllVersions
    ? jobVersions
    : jobVersions.slice(0, MAX_JOB_REFS);

  return (
    <div className="skill-node-detail" aria-label={`${node.label} 节点详情`}>
      <header className="skill-node-detail-header">
        <h3>{node.label}</h3>
        <div className="skill-node-detail-tags">
          <Tag>{`${roleLabels[node.role]} · ${node.techStack}`}</Tag>
          <Tag color={statusTone[node.status]}>{statusLabels[node.status]}</Tag>
        </div>
      </header>

      {aliases.length > 0 ? (
        <section className="skill-node-detail-section" aria-label="别名">
          <h4>别名（{node.aliases.length}）</h4>
          <div className="skill-node-detail-aliases">
            {aliases.map((alias) => (
              <Tag key={alias}>{alias}</Tag>
            ))}
            {aliasOverflow > 0 ? (
              <Tag className="skill-node-detail-overflow">
                {`+${aliasOverflow}`}
              </Tag>
            ) : null}
          </div>
        </section>
      ) : null}

      {isPoint ? (
        <section
          className="skill-node-detail-section"
          aria-label="父能力与兄弟"
        >
          <h4>父能力</h4>
          {parentCapability ? (
            <button
              className="skill-node-detail-link"
              onClick={() => onSelectNode(parentCapability.id)}
              type="button"
            >
              {parentCapability.label}
            </button>
          ) : (
            <p className="skill-node-detail-placeholder">父能力未加载</p>
          )}
          {siblingPoints.length > 0 ? (
            <>
              <h4>兄弟技能点（{siblingPoints.length}）</h4>
              <div className="skill-node-detail-siblings">
                {siblingPoints.map((sibling) => (
                  <button
                    className="skill-node-detail-link"
                    key={sibling.id}
                    onClick={() => onSelectNode(sibling.id)}
                    type="button"
                  >
                    {sibling.label}
                  </button>
                ))}
              </div>
            </>
          ) : null}
        </section>
      ) : siblingPoints.length > 0 ? (
        <section className="skill-node-detail-section" aria-label="下属技能点">
          <h4>下属技能点（{siblingPoints.length}）</h4>
          <div className="skill-node-detail-siblings">
            {siblingPoints.map((sibling) => (
              <button
                className="skill-node-detail-link"
                key={sibling.id}
                onClick={() => onSelectNode(sibling.id)}
                type="button"
              >
                {sibling.label}
              </button>
            ))}
          </div>
        </section>
      ) : null}

      <section className="skill-node-detail-section" aria-label="证据">
        <h4>证据</h4>
        <p className="skill-node-detail-meta">
          {node.evidenceIds.length > 0
            ? `${node.evidenceIds.length} 条证据 · 点击按钮查看原文与质量`
            : "该节点暂无关联证据"}
        </p>
        {node.evidenceIds.length > 0 ? (
          <Button
            block
            icon={<ArrowSquareOut aria-hidden size={15} />}
            onClick={onOpenEvidence}
          >
            查看证据
          </Button>
        ) : null}
      </section>

      <section className="skill-node-detail-section" aria-label="关联岗位版本">
        <h4>关联岗位版本</h4>
        {jobVersions.length > 0 ? (
          <div className="skill-node-detail-siblings">
            {visibleJobVersions.map((ref) => (
              <Link
                className="skill-node-detail-job"
                href={`/skills?job=${encodeURIComponent(ref.versionId)}`}
                key={ref.versionId}
                title={`切换到 ${ref.title}（${ref.versionId}）`}
              >
                {ref.title}
                <Tag color={ref.role === "required" ? "gold" : "default"}>
                  {`${roleLabels[ref.role]}${ref.weight !== null ? ` · ${ref.weight}` : ""}`}
                </Tag>
              </Link>
            ))}
          </div>
        ) : (
          <p className="skill-node-detail-placeholder">
            未进入任何已发布岗位版本。
          </p>
        )}
        {jobVersions.length > MAX_JOB_REFS ? (
          <button
            className="skill-node-detail-more"
            onClick={() => setShowAllVersions((value) => !value)}
            type="button"
          >
            {showAllVersions ? "收起" : `展开全部 ${jobVersions.length} 个版本`}
          </button>
        ) : null}
        <p className="skill-node-detail-meta">
          {signal
            ? `市场信号：${signal.jdMentions} 条 JD 提及（占全部提及 ${Math.round(signal.mentionShare * 100)}%）`
            : "市场信号待接入。"}
        </p>
      </section>
    </div>
  );
}

export function SkillNodeDetailEmpty() {
  return (
    <div className="skill-node-detail-empty" aria-label="节点详情未选中">
      <p>选择节点查看详情与证据</p>
      <p className="skill-node-detail-hint">
        {`别名、关联技能点、证据与岗位版本影响会在选中后展示。`}
      </p>
    </div>
  );
}
