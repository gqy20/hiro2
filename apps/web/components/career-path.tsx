"use client";

import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react";
import { Empty, Tag } from "antd";

import { GapSteps } from "@/components/gap-steps";
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
      <header className="page-heading">
        <div>
          <h1 id="career-path-title" className="sr-only">
            学习路径
          </h1>
          <p>
            {`${fixture.job.title} · ${fixture.job.version} · ${
              gaps.length > 0
                ? `${gaps.length} 项能力缺口，按优先级排序。`
                : "当前没有待补齐的能力缺口。"
            }`}
          </p>
        </div>
        <Link className="career-job-cta" href="/career/diagnosis">
          返回诊断 <ArrowRight aria-hidden size={15} />
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
      {gaps.length > 0 ? (
        <footer className="career-path-footer">
          <div>
            <strong>完成项目后，把成果写进简历</strong>
            <span>简历工作台会按当前目标岗位重新检查能力覆盖。</span>
          </div>
          <Link
            className="career-job-cta"
            href={`/career/resume?job=${encodeURIComponent(fixture.job.version)}`}
          >
            打磨投递简历 <ArrowRight aria-hidden size={15} />
          </Link>
        </footer>
      ) : null}
    </section>
  );
}
