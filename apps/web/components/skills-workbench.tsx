"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { X } from "@phosphor-icons/react";
import { Button, Select } from "antd";

import { AppShell } from "@/components/app-shell";
import { EvidenceDrawer } from "@/components/evidence-drawer";
import { SkillGraph } from "@/components/skill-graph";
import { SkillNodeDetail } from "@/components/skill-node-detail";
import { FixtureState } from "@/components/workflow-ui";
import { WorkflowContext } from "@/components/workflow-context";
import type {
  CapabilityType,
  SkillGraphFixture,
  SkillNode,
  TechStack,
} from "@/lib/skill";
import type { ChangeItem, JobUpdateContext } from "@/lib/job-update";
import type { Evidence } from "@/lib/job-update";

type SkillsWorkbenchProps = {
  fixture: SkillGraphFixture;
  state?: "ready" | "empty" | "error";
};

const roleLabels: Record<SkillNode["role"], string> = {
  required: "必备",
  preferred: "加分",
};

function buildNodeEvidence(node: SkillNode): Evidence[] {
  if (node.evidenceIds.length === 0) return [];
  return node.evidenceIds.map((id, index) => ({
    id,
    source: index % 2 === 0 ? "招聘 JD 汇总" : "技术日报",
    sourceType: index % 2 === 0 ? "招聘 JD" : "技术日报",
    publishedAt: "2026-07-15",
    collectedAt: "2026-08-22",
    quality: 0.85 - index * 0.05,
    excerpt: `Skill ${node.label} 的来源摘要 #${index + 1}`,
    fullText: `技能“${node.label}”的来源说明。`,
    sourceUrl: null,
    stance: index === 0 ? "支持" : "支持",
  }));
}

function toChangeItem(node: SkillNode, context: JobUpdateContext): ChangeItem {
  const confidence = node.status === "removed" ? 0.62 : 0.86;
  return {
    id: node.id,
    kind:
      node.status === "added"
        ? "added"
        : node.status === "removed"
          ? "removed"
          : "modified",
    title: node.label,
    detail: `${context.jobTitle} ${context.targetVersion} 中的${roleLabels[node.role]}${node.pointName ? "技能点" : "能力域"}：${node.label}。`,
    confidence,
    status: node.status === "removed" ? "needs_evidence" : "accepted",
    evidence: buildNodeEvidence(node),
  };
}

export function SkillsWorkbench({
  fixture,
  state = "ready",
}: SkillsWorkbenchProps) {
  const [techStack, setTechStack] = useState<TechStack | "all">("all");
  const [roleFilter, setRoleFilter] = useState<SkillNode["role"] | "all">(
    "all",
  );
  const [capabilityType, setCapabilityType] = useState<CapabilityType | "all">(
    "all",
  );
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [evidenceItem, setEvidenceItem] = useState<ChangeItem | null>(null);
  const [view, setView] = useState<"requirements" | "graph">("requirements");

  const visibleNodes = useMemo(() => {
    return fixture.nodes.filter((node) => {
      if (node.id === "root") return true;
      if (techStack !== "all" && node.techStack !== techStack) return false;
      if (roleFilter !== "all" && node.role !== roleFilter) return false;
      if (capabilityType !== "all") {
        const isPoint = node.pointName !== null;
        if (capabilityType === "capability" && isPoint) return false;
        if (capabilityType === "point" && !isPoint) return false;
      }
      return true;
    });
  }, [fixture.nodes, techStack, roleFilter, capabilityType]);

  const visibleIds = useMemo(
    () => new Set(visibleNodes.map((n) => n.id)),
    [visibleNodes],
  );

  const visibleEdges = useMemo(
    () =>
      fixture.edges.filter(
        (edge) => visibleIds.has(edge.source) && visibleIds.has(edge.target),
      ),
    [fixture.edges, visibleIds],
  );

  const selectedNode = useMemo(
    () => fixture.nodes.find((node) => node.id === selectedId) ?? null,
    [fixture.nodes, selectedId],
  );
  const capabilityGroups = useMemo(() => {
    const groups = new Map<
      string,
      { capability: SkillNode; points: SkillNode[] }
    >();
    visibleNodes
      .filter((node) => node.pointName === null && node.id !== "root")
      .forEach((capability) => {
        groups.set(capability.id, { capability, points: [] });
      });
    visibleNodes
      .filter((node) => node.pointName !== null)
      .forEach((point) => {
        groups.get(point.capabilityId)?.points.push(point);
      });
    return [...groups.values()];
  }, [visibleNodes]);

  function clearFilters() {
    setTechStack("all");
    setRoleFilter("all");
    setCapabilityType("all");
  }

  if (state === "error")
    return (
      <AppShell>
        <FixtureState
          errorText="技能图谱数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  if (state === "empty")
    return (
      <AppShell>
        <FixtureState
          action={
            <Link href="/jobs">
              <Button type="primary">查看岗位更新</Button>
            </Link>
          }
          emptyText="当前图谱暂无可用技能点。"
          state="empty"
        />
      </AppShell>
    );

  return (
    <AppShell>
      <div className="workflow-page">
        <WorkflowContext
          eyebrow="能力全景"
          title={fixture.context.jobTitle}
          stage="查看岗位能力边界"
          next="选择一个能力节点查看证据"
        />
        <section className="skill-workbench" aria-labelledby="skills-title">
          <header className="page-heading">
            <div className="title-with-meta">
              <h1 id="skills-title">技能图谱</h1>
              <span className="page-meta">
                {`${fixture.context.jobTitle} · ${fixture.context.baselineVersion} → ${fixture.context.targetVersion}`}
              </span>
            </div>
          </header>

          <div className="skill-view-tabs" role="tablist" aria-label="能力视图">
            <button
              className={view === "requirements" ? "is-active" : ""}
              onClick={() => setView("requirements")}
              role="tab"
              aria-selected={view === "requirements"}
              type="button"
            >
              岗位要求
            </button>
            <button
              className={view === "graph" ? "is-active" : ""}
              onClick={() => setView("graph")}
              role="tab"
              aria-selected={view === "graph"}
              type="button"
            >
              能力图谱
            </button>
          </div>

          <div className="skill-graph-layout">
            <aside className="skill-graph-toolbar" aria-label="图谱筛选">
              <h2>筛选</h2>
              <label>
                <span>技术栈</span>
                <Select
                  onChange={(value) => setTechStack(value as TechStack | "all")}
                  options={[
                    { label: "全部", value: "all" },
                    ...fixture.filterOptions.techStacks.map((t) => ({
                      label: t,
                      value: t,
                    })),
                  ]}
                  value={techStack}
                />
              </label>
              <label>
                <span>级别</span>
                <Select
                  onChange={(value) =>
                    setRoleFilter(value as SkillNode["role"] | "all")
                  }
                  options={[
                    { label: "全部", value: "all" },
                    ...fixture.filterOptions.roles.map((r) => ({
                      label: roleLabels[r],
                      value: r,
                    })),
                  ]}
                  value={roleFilter}
                />
              </label>
              <label>
                <span>能力类型</span>
                <Select
                  onChange={(value) =>
                    setCapabilityType(value as CapabilityType | "all")
                  }
                  options={[
                    { label: "全部", value: "all" },
                    { label: "能力", value: "capability" },
                    { label: "技能点", value: "point" },
                  ]}
                  value={capabilityType}
                />
              </label>
              <Button
                block
                icon={<X aria-hidden size={15} />}
                onClick={clearFilters}
              >
                清除筛选
              </Button>
              <dl className="skill-graph-counts">
                <div>
                  <dt>当前可见</dt>
                  <dd>{`${visibleNodes.length} / ${fixture.nodes.length}`}</dd>
                </div>
              </dl>
            </aside>

            {view === "requirements" ? (
              <div className="skill-requirements" aria-label="岗位能力要求">
                {(["required", "preferred"] as const).map((role) => (
                  <section key={role} className="skill-requirement-group">
                    <div className="skill-requirement-heading">
                      <h2>{roleLabels[role]}能力</h2>
                      <span>
                        {
                          capabilityGroups.filter(
                            (group) => group.capability.role === role,
                          ).length
                        }{" "}
                        项
                      </span>
                    </div>
                    <div className="skill-requirement-list">
                      {capabilityGroups
                        .filter((group) => group.capability.role === role)
                        .map((group) => (
                          <button
                            className="skill-requirement-item"
                            key={group.capability.id}
                            onClick={() => setSelectedId(group.capability.id)}
                            type="button"
                          >
                            <span>
                              <strong>{group.capability.label}</strong>
                              <small>
                                {group.points.length
                                  ? `${group.points.length} 个技能点`
                                  : "能力域"}
                              </small>
                            </span>
                            <b>
                              {group.capability.status === "added"
                                ? "新增"
                                : group.capability.status === "modified"
                                  ? "修改"
                                  : "查看"}
                            </b>
                          </button>
                        ))}
                    </div>
                  </section>
                ))}
              </div>
            ) : (
              <div className="skill-graph-stage">
                <SkillGraph
                  edges={visibleEdges}
                  nodes={visibleNodes}
                  onSelect={setSelectedId}
                  selectedId={selectedId}
                />
              </div>
            )}

            <aside className="skill-graph-detail" aria-label="节点详情">
              {selectedNode ? (
                <SkillNodeDetail
                  allNodes={fixture.nodes}
                  node={selectedNode}
                  onOpenEvidence={() =>
                    setEvidenceItem(toChangeItem(selectedNode, fixture.context))
                  }
                  onSelectNode={setSelectedId}
                />
              ) : (
                <div className="skill-node-detail-empty">
                  <strong>{fixture.context.jobTitle}</strong>
                  <p>{fixture.context.targetVersion} 岗位能力摘要</p>
                  <p>
                    必备能力{" "}
                    {
                      capabilityGroups.filter(
                        (group) => group.capability.role === "required",
                      ).length
                    }{" "}
                    项 · 加分能力{" "}
                    {
                      capabilityGroups.filter(
                        (group) => group.capability.role === "preferred",
                      ).length
                    }{" "}
                    项
                  </p>
                  <p>选择左侧能力查看技能点、别名和证据。</p>
                </div>
              )}
            </aside>
          </div>
        </section>
      </div>

      <EvidenceDrawer
        context={fixture.context}
        item={evidenceItem}
        onClose={() => setEvidenceItem(null)}
      />
    </AppShell>
  );
}
