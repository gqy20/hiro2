const SKILL_LABELS: Record<string, string> = {
  cap_01: "LLM 应用",
  cap_02: "Prompt 工程",
  cap_03: "模型微调",
  cap_04: "AI Agent",
  cap_05: "多模态 AI",
  cap_06: "RAG / 知识库",
  cap_07: "Python",
  cap_08: "SQL / 数据库",
  cap_09: "大数据处理",
  cap_10: "数据标注",
  cap_11: "数据可视化",
  cap_12: "机器学习 / 深度学习",
  cap_13: "云计算",
  cap_14: "API 开发",
  cap_15: "系统架构",
  cap_16: "物联网 / IoT",
  cap_17: "嵌入式 / 硬件",
  cap_18: "自动化运维",
  cap_19: "AI 伦理与合规",
  cap_20: "法规与审计",
  cap_21: "领域知识",
  cap_22: "产品思维",
  cap_23: "项目管理",
  cap_24: "培训与教学",
  cap_25: "英语",
  cap_26: "跨部门沟通",
  cap_27: "团队管理",
  cap_28: "战略思维",
  cap_29: "创新思维",
  cap_30: "安全与风控意识",
};

export function skillLabel(id: string): string {
  return SKILL_LABELS[id] ?? id;
}

export function skillDisplay(id: string): string {
  const label = skillLabel(id);
  return label === id ? id : `${label}（${id}）`;
}

export function allSkillOptions(): Array<{ id: string; label: string }> {
  return Object.entries(SKILL_LABELS).map(([id, label]) => ({ id, label }));
}
