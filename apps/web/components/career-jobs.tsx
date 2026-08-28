"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowRight } from "@phosphor-icons/react";
import { Empty, Segmented, Tag } from "antd";

import type { PublishedJobsView } from "@/lib/career-jobs";

const ALL = "全部";

export function CareerJobs({ view }: { view: PublishedJobsView }) {
  const groups = useMemo(
    () => [ALL, ...new Set(view.jobs.map((j) => j.group).filter(Boolean))],
    [view.jobs],
  );
  const [group, setGroup] = useState(ALL);
  const jobs = useMemo(
    () =>
      group === ALL ? view.jobs : view.jobs.filter((j) => j.group === group),
    [view.jobs, group],
  );

  return (
    <section aria-labelledby="career-jobs-title" className="career-jobs">
      <header className="page-heading">
        <div>
          <h1 id="career-jobs-title">目标岗位</h1>
          <p>全部岗位均为已发布岗位版本，诊断可回溯到具体版本与证据。</p>
        </div>
        <Segmented
          aria-label="岗位族筛选"
          onChange={(v) => setGroup(v as string)}
          options={groups}
          value={group}
        />
      </header>
      {jobs.length === 0 ? (
        <Empty description="该岗位族暂无已发布岗位版本。" />
      ) : (
        <div className="career-jobs-grid">
          {jobs.map((job) => (
            <article className="career-job-card" key={job.version_id}>
              <header>
                <h2>{job.title}</h2>
                <Tag>{job.version_id}</Tag>
              </header>
              <p className="career-job-duty">{job.duty || "职责说明整理中。"}</p>
              <dl className="career-job-meta">
                <div>
                  <dt>必备能力</dt>
                  <dd>{job.required_count} 项</dd>
                </div>
                <div>
                  <dt>加分能力</dt>
                  <dd>{job.preferred_count} 项</dd>
                </div>
                <div>
                  <dt>生效时间</dt>
                  <dd>{job.valid_from || "—"}</dd>
                </div>
              </dl>
              <Link
                aria-label={`开始诊断 ${job.title}`}
                className="career-job-cta"
                href="/diagnosis"
              >
                开始诊断 <ArrowRight aria-hidden size={15} />
              </Link>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
