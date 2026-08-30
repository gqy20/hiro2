"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight } from "@phosphor-icons/react";
import { Empty, Segmented, Tag } from "antd";

import { saveCandidateTarget } from "@/lib/api/queries";
import type { PublishedJobsView } from "@/lib/career-jobs";

const ALL = "全部";

export function CareerJobs({ view }: { view: PublishedJobsView }) {
  const router = useRouter();
  const groups = useMemo(
    () => [ALL, ...new Set(view.jobs.map((j) => j.group).filter(Boolean))],
    [view.jobs],
  );
  const [group, setGroup] = useState(ALL);
  const [currentTarget, setCurrentTarget] = useState(
    view.jobs.find((job) => job.version_id === "ai-agent-v2")?.version_id ??
      view.jobs[0]?.version_id ??
      "",
  );
  const [selecting, setSelecting] = useState<string | null>(null);
  const jobs = useMemo(
    () =>
      group === ALL ? view.jobs : view.jobs.filter((j) => j.group === group),
    [view.jobs, group],
  );

  async function startDiagnosis(versionId: string) {
    setSelecting(versionId);
    await saveCandidateTarget("synth_agent_senior_02", versionId);
    setCurrentTarget(versionId);
    router.push(`/career/diagnosis?job=${encodeURIComponent(versionId)}`);
  }

  return (
    <section aria-labelledby="career-jobs-title" className="career-jobs">
      <header className="page-heading">
        <div>
          <h1 id="career-jobs-title" className="sr-only">
            目标岗位
          </h1>
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
            <article
              className={`career-job-card ${
                job.version_id === currentTarget ? "is-current" : ""
              }`}
              key={job.version_id}
            >
              <header>
                <h2>{job.title}</h2>
                <Tag
                  color={job.version_id === currentTarget ? "blue" : undefined}
                >
                  {job.version_id === currentTarget ? "当前目标" : job.group}
                </Tag>
              </header>
              <p className="career-job-duty">
                {job.duty || "职责说明整理中。"}
              </p>
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
              <button
                aria-label={`开始诊断 ${job.title}`}
                className="career-job-cta"
                disabled={selecting !== null}
                onClick={() => void startDiagnosis(job.version_id)}
                type="button"
              >
                {selecting === job.version_id
                  ? "正在进入…"
                  : job.version_id === currentTarget
                    ? "查看诊断"
                    : "设为目标并诊断"}
                <ArrowRight aria-hidden size={15} />
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
