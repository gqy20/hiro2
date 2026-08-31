"use client";

// 工作区引导层：AntD 原生 Tour（原生优先，不引第三方引导库）。
// 锚点固定选顶栏导航项（当前工作区的功能地图，任何页面都存在、不失效）；
// 首步不锚定居中欢迎，末步指向「使用引导」问号按钮本身（解释如何重开）。

import { Tour } from "antd";
import type { TourProps } from "antd";

type Workspace = "recruiting" | "career" | "data";

type Step = { title: string; description: string; target?: string };

const NAV_ANCHOR = (href: string) => `[data-tour="${href}"]`;

const STEPS: Record<Workspace, Step[]> = {
  recruiting: [
    {
      title: "欢迎来到招聘工作区",
      description:
        "核心闭环：发现岗位变化 → 审核证据 → 发布岗位版本 → 诊断候选人。顶部导航对应每一步。",
    },
    {
      title: "工作台",
      description: "总览当前岗位、待审核变化与下一步行动。",
      target: NAV_ANCHOR("/"),
    },
    {
      title: "岗位发现",
      description: "市场新出现的岗位候选，可查看证据、编辑定义并接受或拒绝。",
      target: NAV_ANCHOR("/new-jobs"),
    },
    {
      title: "我的岗位",
      description: "已发布岗位版本与系统检测到的变化草稿。",
      target: NAV_ANCHOR("/positions"),
    },
    {
      title: "能力全景",
      description: "岗位能力图谱：必备/加分技能、技能点与关联证据。",
      target: NAV_ANCHOR("/skills"),
    },
    {
      title: "候选诊断",
      description: "按已发布岗位版本评估候选人：缺口、依据与提升建议。",
      target: NAV_ANCHOR("/diagnosis"),
    },
    {
      title: "使用引导",
      description: "任何时候点右侧问号，可重新查看本工作区的引导。",
      target: ".help-trigger",
    },
  ],
  career: [
    {
      title: "欢迎来到求职工作区",
      description:
        "核心闭环：选目标岗位 → 诊断能力差距 → 按学习路径提升 → 打磨简历投递。",
    },
    {
      title: "目标岗位",
      description: "浏览全部已发布岗位，设为目标并开始诊断。",
      target: NAV_ANCHOR("/career/jobs"),
    },
    {
      title: "我的画像",
      description: "维护技能、熟练度与能力证明，保存后驱动诊断。",
      target: NAV_ANCHOR("/profile"),
    },
    {
      title: "人岗诊断",
      description: "查看必备能力满足度、关键短板与岗位依据。",
      target: NAV_ANCHOR("/career/diagnosis"),
    },
    {
      title: "学习路径",
      description: "按缺口排序的学练赛证路径，含证书与竞赛推荐。",
      target: NAV_ANCHOR("/career/path"),
    },
    {
      title: "简历工作台",
      description: "编辑投递简历、获取岗位对齐建议并生成 PDF。",
      target: NAV_ANCHOR("/career/resume"),
    },
    {
      title: "使用引导",
      description: "任何时候点右侧问号，可重新查看本工作区的引导。",
      target: ".help-trigger",
    },
  ],
  data: [
    {
      title: "欢迎来到数据工作区",
      description:
        "这里是系统的可信度后台：审核证据、维护质量、观察趋势，支撑岗位与诊断的可信。",
    },
    {
      title: "总览",
      description: "数据规模、来源与导入状态的统一入口。",
      target: NAV_ANCHOR("/data"),
    },
    {
      title: "数据资产",
      description: "数据集版本、记录与来源清单的详情。",
      target: NAV_ANCHOR("/data/assets"),
    },
    {
      title: "证据审核",
      description: "领取审核任务，对系统抽取/预测结果做人工决策。",
      target: NAV_ANCHOR("/tasks"),
    },
    {
      title: "评测质量",
      description: "评测指标、错误案例与新旧运行对比。",
      target: NAV_ANCHOR("/evaluation"),
    },
    {
      title: "趋势洞察",
      description: "能力需求趋势、信号流与预测复盘。",
      target: NAV_ANCHOR("/temporal"),
    },
    {
      title: "使用引导",
      description: "任何时候点右侧问号，可重新查看本工作区的引导。",
      target: ".help-trigger",
    },
  ],
};

export function OnboardingTour({
  open,
  onClose,
  workspace,
}: {
  open: boolean;
  onClose: () => void;
  workspace: Workspace;
}) {
  // antd Tour 的 target 类型要求 `() => HTMLElement` 或 `null`；导航锚点在当前
  // 工作区下必然存在（Tour 只在该工作区激活时打开），用非空断言收窄类型。
  const steps: TourProps["steps"] = STEPS[workspace].map((step) => {
    const selector = step.target;
    return {
      title: step.title,
      description: step.description,
      target: selector
        ? () => document.querySelector(selector) as HTMLElement
        : null,
    };
  });
  return (
    <Tour
      open={open}
      onClose={onClose}
      steps={steps}
      indicatorsRender={(current, total) => (
        <span>{`${current + 1} / ${total}`}</span>
      )}
    />
  );
}
