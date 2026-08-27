// F-T4.10/11 任务 mock：DTO 严格照 docs/contracts.md:283-310。
// 数据源：forecast_review 用 lib/temporal-fixture.ts 的 forecasts；
// job_review 用 data/fixtures/job_update.json 的 changes。

export type ReviewTaskType =
  | "jd_annotation"
  | "role_level"
  | "skill_mapping"
  | "evidence_audit"
  | "forecast_review"
  | "job_review"
  | "match_review"
  | "ux_test";

export type ReviewTaskStatus =
  | "PENDING"
  | "CLAIMED"
  | "IN_REVIEW"
  | "SUBMITTED"
  | "ADJUDICATING"
  | "RESOLVED";

export type ReviewDecision = "ACCEPT" | "MODIFY" | "REJECT" | "UNKNOWN";
export type ReviewPriority = "high" | "medium" | "low";

export type ReviewTask = {
  task_id: string;
  task_type: ReviewTaskType;
  source_record_id: string;
  run_id: string;
  dataset_version: string;
  priority: ReviewPriority;
  assignee_id: string | null;
  status: ReviewTaskStatus;
  system_output: Record<string, unknown>;
  evidence_ids: string[];
  needs_dual_review?: boolean;
};

const TASK_TYPE_LABEL: Record<ReviewTaskType, string> = {
  jd_annotation: "JD 标注",
  role_level: "角色层级",
  skill_mapping: "技能映射",
  evidence_audit: "证据审计",
  forecast_review: "预测复核",
  job_review: "岗位复核",
  match_review: "匹配复核",
  ux_test: "UX 测试",
};

const STATUS_TONE: Record<ReviewTaskStatus, string> = {
  PENDING: "default",
  CLAIMED: "blue",
  IN_REVIEW: "gold",
  SUBMITTED: "cyan",
  ADJUDICATING: "purple",
  RESOLVED: "green",
};

const PRIORITY_TONE: Record<ReviewPriority, string> = {
  high: "red",
  medium: "gold",
  low: "default",
};

export const TASK_TYPE_LABELS = TASK_TYPE_LABEL;
export const REVIEW_STATUS_TONES = STATUS_TONE;
export const REVIEW_PRIORITY_TONES = PRIORITY_TONE;

export function buildMockTasks(): ReviewTask[] {
  const tasks: ReviewTask[] = [
    {
      task_id: "task-001",
      task_type: "forecast_review",
      source_record_id: "FCT-cap_01-h30-0",
      run_id: "BT-30-1",
      dataset_version: "wechat-mp-2026-07",
      priority: "high",
      assignee_id: null,
      status: "PENDING",
      system_output: {
        skill_id: "cap_01",
        predicted_direction: "flat",
        confidence: 0.4,
        horizon_days: 30,
        as_of_date: "2026-07-01",
        current_phase: "平稳期",
        reason_summary:
          "cap_01 在 2026-07 预测为平稳，置信度 0.4，需要人工确认",
      },
      evidence_ids: ["ev-skill-001", "ev-skill-002", "ev-skill-003"],
      needs_dual_review: false,
    },
    {
      task_id: "task-002",
      task_type: "forecast_review",
      source_record_id: "FCT-cap_04-h30-2",
      run_id: "BT-30-1",
      dataset_version: "wechat-mp-2026-07",
      priority: "high",
      assignee_id: null,
      status: "PENDING",
      system_output: {
        skill_id: "cap_04",
        predicted_direction: "up",
        confidence: 0.85,
        horizon_days: 30,
        as_of_date: "2026-07-01",
        current_phase: "上升期",
        reason_summary:
          "cap_04 (AI Agent) 预测上升，置信度 0.85，建议升级为必备技能",
      },
      evidence_ids: [
        "ev-skill-010",
        "ev-skill-011",
        "ev-skill-012",
        "ev-skill-013",
      ],
      needs_dual_review: true,
    },
    {
      task_id: "task-003",
      task_type: "forecast_review",
      source_record_id: "FCT-cap_05-h30-3",
      run_id: "BT-30-1",
      dataset_version: "wechat-mp-2026-07",
      priority: "medium",
      assignee_id: "reviewer-002",
      status: "CLAIMED",
      system_output: {
        skill_id: "cap_05",
        predicted_direction: "up",
        confidence: 0.72,
        horizon_days: 30,
        as_of_date: "2026-07-01",
        current_phase: "上升期",
        reason_summary: "cap_05 (多模态AI) 预测上升，建议加入加分技能",
      },
      evidence_ids: ["ev-skill-014", "ev-skill-015"],
      needs_dual_review: false,
    },
    {
      task_id: "task-004",
      task_type: "job_review",
      source_record_id: "change-智能体编排",
      run_id: "BT-30-1",
      dataset_version: "fixture-2026-08",
      priority: "high",
      assignee_id: "reviewer-001",
      status: "IN_REVIEW",
      system_output: {
        change_type: "added",
        title: "智能体编排",
        confidence: 0.91,
        evidence_summary: "招聘 JD 19 条 / 工具日报 4 条支持",
        proposed_level: "required",
      },
      evidence_ids: ["ev-091", "ev-104"],
    },
    {
      task_id: "task-005",
      task_type: "job_review",
      source_record_id: "change-仅提示词优化",
      run_id: "BT-30-1",
      dataset_version: "fixture-2026-08",
      priority: "medium",
      assignee_id: "reviewer-001",
      status: "PENDING",
      system_output: {
        change_type: "removed",
        title: "仅提示词优化",
        confidence: 0.68,
        evidence_summary: "招聘 JD 1 条 / 职业标准 1 条（其中 1 条反证）",
        proposed_level: "out_of_scope",
      },
      evidence_ids: ["ev-122", "ev-126"],
      needs_dual_review: true,
    },
  ];
  return tasks;
}
