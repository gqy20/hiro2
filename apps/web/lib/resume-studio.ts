// 简历工作台类型与 mock（对应后端 ResumeDraft / advice 端点）。

export type DraftExperience = {
  company: string;
  role: string;
  period: string;
  bullets: string[];
};

export type DraftProject = { name: string; desc: string; bullets: string[] };

export type DraftEducation = {
  school: string;
  major: string;
  degree: string;
  period: string;
};

export type ResumeDraftInput = {
  name: string;
  contact: string;
  title: string;
  summary: string;
  skills: string[];
  experiences: DraftExperience[];
  projects: DraftProject[];
  education: DraftEducation[];
};

export type AdviceItemView = {
  kind: "coverage" | "specificity" | "structure";
  severity: "high" | "medium" | "low";
  title: string;
  detail: string;
  suggestion: string;
  skill_id?: string | null;
  evidence: Record<string, string>;
};

export type AdviceView = {
  job_version_id: string;
  job_title: string;
  required_total: number;
  required_covered: number;
  advice: AdviceItemView[];
  note?: string;
};

export function emptyDraft(): ResumeDraftInput {
  return {
    name: "",
    contact: "",
    title: "",
    summary: "",
    skills: [],
    experiences: [{ company: "", role: "", period: "", bullets: [""] }],
    projects: [],
    education: [{ school: "", major: "", degree: "", period: "" }],
  };
}

export function buildMockAdvice(jobTitle: string): AdviceView {
  return {
    job_version_id: "mock",
    job_title: jobTitle,
    required_total: 8,
    required_covered: 3,
    advice: [
      {
        kind: "coverage",
        severity: "high",
        title: "未体现目标岗位必备技能：RAG/知识库",
        detail: `目标岗位《${jobTitle}》的必备技能 RAG/知识库（市场权重 10.6%）在你的技能区未出现`,
        suggestion: "有相关经验时，在技能区或经历中补充该能力的具体表述",
        skill_id: "cap_06",
        evidence: { job_version_id: "mock", weight: "10.6%", jd_count: "56" },
      },
      {
        kind: "specificity",
        severity: "low",
        title: "「LangChain」可以更具体",
        detail:
          "该能力域在岗位画像中包含技能点：MCP、工具调用、联网搜索、深度研究、记忆",
        suggestion:
          "bullet 写出具体环节（选型/评测/调优），比罗列名词更有说服力",
        skill_id: "cap_04",
        evidence: { job_version_id: "mock", points: "MCP、工具调用、记忆" },
      },
      {
        kind: "structure",
        severity: "medium",
        title: "缺少个人概述",
        detail: "招聘方第一屏看不到你的定位",
        suggestion: "补 2~3 句：方向 + 年限 + 最相关的一项成果",
        evidence: {},
      },
    ],
    note: "mock 建议数据",
  };
}
