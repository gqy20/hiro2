import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DashboardOverview } from "@/lib/dashboard";

export default async function PositionsPage() {
  const dashboard = isMockMode()
    ? null
    : await apiFetch<DashboardOverview>("/dashboard/overview");
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
                  <p>{job.version} · {job.status}</p>
                </div>
                <dl className="position-card-meta">
                  <div><dt>待处理变化</dt><dd>{job.pending}</dd></div>
                  <div><dt>下一步</dt><dd>审核并发布</dd></div>
                </dl>
                <div className="position-card-actions">
                  <Link href={job.href}>继续审核 →</Link>
                  <Link href="/diagnosis">候选人诊断</Link>
                </div>
              </article>
            ))}
          </section>
          <section className="positions-create" aria-label="岗位操作">
            <div>
              <h2>需要建立新的岗位标准？</h2>
              <p>从市场中的新岗位候选开始，形成可审核的岗位定义。</p>
            </div>
            <Link className="dashboard-primary-action" href="/new-jobs">查看新岗位候选</Link>
          </section>
        </main>
      </div>
    </AppShell>
  );
}
