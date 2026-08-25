// 技能图谱相关类型。
//
// ponytail: 节点 ID 沿用 contracts.md 约定（cap_xx / cap_xx.point_name）；
// 仅补前端渲染所需的 role / status / position / aliases，不重定义 DTO。

import type { JobUpdateContext } from "@/lib/job-update";

export type SkillRole = "required" | "preferred";
export type SkillStatus = "added" | "removed" | "modified" | "stable";
export type CapabilityType = "capability" | "point";
export type TechStack = "LLM" | "Agent" | "RAG" | "多模态" | "数据" | "工程" | "治理";

export type SkillNode = {
  id: string;
  label: string;
  capabilityId: string;
  pointName: string | null;
  role: SkillRole;
  status: SkillStatus;
  aliases: string[];
  evidenceIds: string[];
  position: { x: number; y: number };
  techStack: TechStack;
};

export type SkillEdge = {
  id: string;
  source: string;
  target: string;
};

export type SkillGraphFixture = {
  fixtureVersion: string;
  mode: "synthetic";
  run: { id: string; datasetVersion: string; status: "REVIEWING" | "FAILED" };
  context: JobUpdateContext;
  nodes: SkillNode[];
  edges: SkillEdge[];
  filterOptions: {
    techStacks: TechStack[];
    roles: SkillRole[];
    capabilityTypes: CapabilityType[];
  };
};