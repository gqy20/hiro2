"use client";

import { ThoughtChain } from "@ant-design/x";
import { ClockCounterClockwise, SpinnerGap } from "@phosphor-icons/react";
import { Tag } from "antd";

import type { ProgressStep } from "@/lib/job-update";

type ReviewProgressProps = {
  running: boolean;
  runId: string;
  steps: ProgressStep[];
};

export function ReviewProgress({ running, runId, steps }: ReviewProgressProps) {
  const renderedSteps = steps.map((step, index) => ({
    description: step.detail,
    icon:
      step.state === "active" && running ? (
        <SpinnerGap aria-hidden className="spin" size={16} />
      ) : (
        false
      ),
    key: step.id,
    status:
      step.state === "finished"
        ? ("success" as const)
        : running && index === 2
          ? ("loading" as const)
          : ("success" as const),
    title: step.label,
  }));

  return (
    <section className="review-progress" aria-labelledby="progress-title">
      <div className="section-heading">
        <div className="inline-heading">
          <h2 id="progress-title">分析记录</h2>
          <span>{runId}</span>
        </div>
        <Tag
          color={running ? "processing" : "gold"}
          icon={
            running ? (
              <SpinnerGap className="spin" />
            ) : (
              <ClockCounterClockwise />
            )
          }
        >
          {running ? "分析中" : "待审核"}
        </Tag>
      </div>
      <ThoughtChain items={renderedSteps} line="dashed" />
    </section>
  );
}
