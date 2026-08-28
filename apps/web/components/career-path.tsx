"use client";

import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react";
import { Empty, Tag } from "antd";

import { GapSteps } from "@/components/gap-steps";
import { WorkflowContext } from "@/components/workflow-context";
import type { DiagnosisFixture } from "@/lib/diagnosis";

type Gap = DiagnosisFixture["report"]["gaps"][number];

const PRIORITY_LABEL: Record<Gap["priority"], string> = {
  high: "优先补齐",
  medium: "巩固提升",
};

export function CareerPath({ fixture }: { fixture: DiagnosisFixture }) {
  const gaps = [...fixture.report.gaps].sort((a, b) =>
    a.priority === b.priority ? 0 : a.priority === "high" ? -1 : 1,
  );
  return (
    <section aria-labelledby="career-path-title" className="career-path">
      <WorkflowContext
        eyebrow="学习路径"
        title={fixture.job.title}
        stage={`目标版本 ${fixture.job.version}`}
        next="按顺序补齐缺口后重新诊断"
        href="/diagnosis"
      />
      <header className="page-heading">
        <div>
          <h1 id="career-path-title">学习路径</h1>
          <p>
            {gaps.length > 0
              ? `${gaps.length} 项能力缺口，按优先级排序。`
              : "当前没有待补齐的能力缺口。"}
          </p>
        </div>
        <Link className="career-job-cta" href="/diagnosis">
          更新画像后重新诊断 <ArrowRight aria-hidden size={15} />
        </Link>
      </header>
      {gaps.length === 0 ? (
        <Empty description="已具备全部必备能力，可以查看其他目标岗位。" />
      ) : (
        <ol className="career-path-list">
          {gaps.map((gap, i) => (
            <li className="career-path-item" key={gap.skill}>
              <header>
                <span className="career-path-index">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <h2>{gap.skill}</h2>
                <Tag color={gap.priority === "high" ? "red" : "blue"}>
                  {PRIORITY_LABEL[gap.priority]}
                </Tag>
              </header>
              {gap.reason ? (
                <p className="career-path-reason">{gap.reason}</p>
              ) : null}
              <GapSteps gap={gap} />
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
