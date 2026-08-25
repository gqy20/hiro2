// 前端 API View Model 集中入口。
//
// 当前只放岗位更新页所需的类型，复用既有 `lib/job-update.ts` 的定义避免重复。
// 后续每迁移一个页面，按需在此处扩展对应的 DTO / View Model 类型。
export type {
  JobUpdateFixture as JobUpdateView,
  Evidence,
  ReviewStatus,
  ChangeKind,
  ChangeItem,
  SourceType,
  EvidenceStance,
  ProgressStep,
  JobUpdateContext,
} from "@/lib/job-update";

export type {
  SkillGraphFixture as SkillGraphView,
  SkillNode,
  SkillEdge,
  SkillRole,
  SkillStatus,
  CapabilityType,
  TechStack,
} from "@/lib/skill";