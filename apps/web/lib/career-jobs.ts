// 求职区目标岗位页 View Model 与 mock fixture。
// 对应后端 GET /api/v1/jobs/published（backend/application/joblist.py）。

export type PublishedJob = {
  job_id: string;
  version_id: string;
  title: string;
  group: string;
  duty: string;
  required_count: number;
  preferred_count: number;
  valid_from: string;
  published_at: string;
};

export type PublishedJobsView = {
  jobs: PublishedJob[];
  total: number;
};

export function buildMockJobs(): PublishedJobsView {
  const jobs: PublishedJob[] = [
    {
      job_id: "job_pos_02_agent",
      version_id: "ai-agent-v2",
      title: "AI Agent 工程师",
      group: "AI研发",
      duty: "负责Agent框架搭建，明确目标、输入输出、关键指标和交付标准，按计划完成方案设计、实施与复盘。",
      required_count: 5,
      preferred_count: 5,
      valid_from: "2026-07",
      published_at: "2026-08-20T10:00:00",
    },
    {
      job_id: "job_pos_01",
      version_id: "llm-algo-v2",
      title: "大模型算法工程师",
      group: "AI研发",
      duty: "负责LLM预训练，明确目标、输入输出、关键指标和交付标准，按计划完成方案设计、实施与复盘。",
      required_count: 5,
      preferred_count: 5,
      valid_from: "2026-06",
      published_at: "2026-08-18T10:00:00",
    },
    {
      job_id: "job_pos_11",
      version_id: "bigdata-v3",
      title: "大数据工程师",
      group: "大数据",
      duty: "负责数据平台建设，明确目标、输入输出、关键指标和交付标准，按计划完成方案设计、实施与复盘。",
      required_count: 5,
      preferred_count: 4,
      valid_from: "2026-06",
      published_at: "2026-08-15T10:00:00",
    },
    {
      job_id: "job_pos_06",
      version_id: "ai-pm-v2",
      title: "AI产品经理",
      group: "AI应用",
      duty: "负责AI产品规划，明确目标、输入输出、关键指标和交付标准，按计划完成方案设计、实施与复盘。",
      required_count: 4,
      preferred_count: 4,
      valid_from: "2026-05",
      published_at: "2026-08-10T10:00:00",
    },
  ];
  return { jobs, total: jobs.length };
}
