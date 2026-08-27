"use client";

import { ClockCounterClockwise, SpinnerGap } from "@phosphor-icons/react";
import { Tag } from "antd";

import type { ProgressStep } from "@/lib/job-update";

type ReviewProgressProps = {
  running: boolean;
  runId: string;
  steps: ProgressStep[];
};

export function ReviewProgress({ running, runId, steps }: ReviewProgressProps) {
  const shortRunId =
    runId.length > 20 ? `${runId.slice(0, 10)}…${runId.slice(-6)}` : runId;
  return (
    <section className="review-progress" aria-labelledby="progress-title">
      <div className="section-heading">
        <div className="inline-heading">
          <h2 id="progress-title">分析记录</h2>
          <span title={runId}>{shortRunId}</span>
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
      <ul className="review-progress-steps">
        {steps.map((step) => (
          <li key={step.id} className={`review-progress-step is-${step.state}`}>
            <span className="review-progress-step-dot" aria-hidden>
              {step.state === "active" && running ? (
                <SpinnerGap className="spin" size={14} />
              ) : null}
            </span>
            <strong>{step.label}</strong>
            <span>{step.detail}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}
