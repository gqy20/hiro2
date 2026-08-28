"use client";

// 学练赛证四段共享渲染：学习知识点 -> 项目练习 -> 实践评测 -> 能力证明。
// 供学习路径页（career-path）与诊断页成长计划（diagnosis-workbench）复用。

export type GapStepsGap = {
  action: string;
  practice?: string;
  evaluate?: string;
  certify?: string;
};

export function GapSteps({
  gap,
  className = "career-path-steps",
}: {
  gap: GapStepsGap;
  className?: string;
}) {
  const steps = [
    { key: "学", text: gap.action },
    { key: "练", text: gap.practice },
    { key: "赛", text: gap.evaluate },
    { key: "证", text: gap.certify },
  ].filter((s) => s.text);
  if (steps.length === 0) return null;
  return (
    <ol className={className}>
      {steps.map((s) => (
        <li key={s.key}>
          <b>{s.key}</b>
          <span>{s.text}</span>
        </li>
      ))}
    </ol>
  );
}
