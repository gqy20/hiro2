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

export type {
  NewJobsFixture as NewJobsView,
  EmergingJobCandidate,
} from "@/lib/new-jobs";

export type {
  DiagnosisFixture as DiagnosisView,
  SkillMatch,
  ProjectEntry,
  UserCorrection,
} from "@/lib/diagnosis";

export type { QualityOverview } from "@/lib/quality";

export type { PublishedJob, PublishedJobsView } from "@/lib/career-jobs";

// 快照差异检测结果：字段名与后端 DetectedChangesVM（snake_case）保持一致，
// 前端不得另造驼峰别名（见 contracts.md 「岗位变化检测」条目）。
export type DetectedChangeType = "add" | "grow" | "shrink" | "remove";

export type DetectedChange = {
  skill_id: string;
  name: string;
  change_type: DetectedChangeType;
  base_share: number;
  obs_share: number;
  base_mentions: number;
  obs_mentions: number;
};

export type DetectedJob = {
  position_id: string;
  job: string;
  base: string;
  obs: string;
  base_jds: number;
  obs_jds: number;
  review_status: string;
  changes: DetectedChange[];
};

export type DetectedChangesView = {
  base: string;
  obs: string;
  jobs: DetectedJob[];
  changes_total: number;
};

// GET /api/v1/candidates 的候选人摘要（招聘模式候选人切换器）。
export type CandidateSummary = {
  id: string;
  name: string;
  education?: string;
  experienceYears?: number | null;
  skills?: number;
};
