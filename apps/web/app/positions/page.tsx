import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DashboardOverview } from "@/lib/dashboard";

type DetectedChange = {
  skillId: string;
  name: string;
  changeType: string;
  baseShare: number;
  obsShare: number;
};

type Detected = {
  base: string;
  obs: string;
  changesTotal: number;
  jobs: {
    positionId: string;
    job: string;
    baseJds: number;
    obsJds: number;
    changes: DetectedChange[];
  }[];
};

export default async function PositionsPage() {
  const dashboard = isMockMode()
    ? null
    : await apiFetch<DashboardOverview>("/dashboard/overview");
  const detected = isMockMode()
    ? null
    : await apiFetch<Detected>("/jobs/detected-changes");
  const jobs = dashboard?.jobs ?? [
    {
      title: "AI 应用工程师（综合）",
      version: "v1.5",
      status: "待审核",
      pending: 13,
      href: "/jobs",
    },
  ];

  return (
    <AppShell>
      <div className="workflow-page">
        <main className="positions-page" aria-labelledby="positions-title">
          <header className="page-heading">
            <h1 id="positions-title">我的岗位</h1>
            <p>查看岗位当前版本、变化状态和候选人诊断入口。</p>
          </header>
          <section className="positions-list" aria-label="岗位列表">
            {jobs.map((job) => (
              <article className="position-card" key={job.href}>
                <div className="position-card-main">
                  <h2>{job.title}</h2>
                  <p>
                    {job.version} · {job.status}
                  </p>
                </div>
                <dl className="position-card-meta">
                  <div>
                    <dt>待处理变化</dt>
                    <dd>{job.pending}</dd>
                  </div>
                  <div>
                    <dt>下一步</dt>
                    <dd>审核并发布</dd>
                  </div>
                </dl>
                <div className="position-card-actions">
                  <Link href={job.href}>
                    {job.pending > 0 ? `审核变化（${job.pending}）→` : "查看版本 →"}
                  </Link>
                  <Link href="/diagnosis">候选人诊断</Link>
                </div>
              </article>
            ))}
          </section>
          <section
            className="positions-detected"
            aria-label="系统检测到的岗位变化"
          >
            <header className="page-heading">
              <div className="title-with-meta">
                <h2>系统检测到的岗位变化</h2>
                <span className="page-meta">
                  {detected
                    ? `快照 Diff：${detected.base} → ${detected.obs} · ${detected.changesTotal} 项待复核`
                    : "接入真实后端后，快照 Diff 自动检出岗位技能变化草稿"}
                </span>
              </div>
            </header>
            {detected ? (
              <ul className="detected-list">
                {detected.jobs.slice(0, 6).map((job) => (
                  <li className="detected-item" key={job.positionId}>
                    <div>
                      <strong>{job.job}</strong>
                      <small>
                        {job.baseJds} → {job.obsJds} 条 JD ·{" "}
                        {job.changes.length} 项变化
                      </small>
                    </div>
                    <div className="training-tags">
                      {job.changes.slice(0, 3).map((ch) => (
                        <span
                          className={`detected-tag detected-${ch.changeType}`}
                          key={ch.skillId}
                        >
                          {`${ch.name} ${Math.round(ch.baseShare * 100)}%→${Math.round(
                            ch.obsShare * 100,
                          )}%`}
                        </span>
                      ))}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="publish-hint">
                数据管线：每日快照归档 → snapshotdiff 按岗位对比技能份额 →
                变化草稿在此展示，人工复核后升版发布。
              </p>
            )}
          </section>
          <section className="positions-create" aria-label="岗位操作">
            <div>
              <h2>需要建立新的岗位标准？</h2>
              <p>从市场中的新岗位候选开始，形成可审核的岗位定义。</p>
            </div>
            <Link className="dashboard-primary-action" href="/new-jobs">
              查看新岗位候选
            </Link>
          </section>
        </main>
      </div>
    </AppShell>
  );
}
