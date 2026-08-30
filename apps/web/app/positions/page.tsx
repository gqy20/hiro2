import Link from "next/link";

import { AppShell } from "@/components/app-shell";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DetectedChangesView } from "@/lib/api/types";
import type { DashboardOverview } from "@/lib/dashboard";
import { loadDetectedChangesFixture } from "@/lib/job-fixture";

export const metadata = { title: "我的岗位" };

// ponytail: 字段名沿用后端 DetectedChangesVM 的 snake_case，不另造驼峰别名。
async function fetchDetectedServer(): Promise<DetectedChangesView | null> {
  if (isMockMode()) return loadDetectedChangesFixture();
  try {
    return await apiFetch<DetectedChangesView>("/jobs/detected-changes");
  } catch {
    return null; // 检测草稿不可用时保留岗位卡与提示，不阻断整页
  }
}

export default async function PositionsPage() {
  const dashboard = isMockMode()
    ? null
    : await apiFetch<DashboardOverview>("/dashboard/overview");
  const detected = await fetchDetectedServer();
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
            <h1 id="positions-title" className="sr-only">
              我的岗位
            </h1>
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
                    {job.pending > 0
                      ? `审核变化（${job.pending}）→`
                      : "查看版本 →"}
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
                    ? `快照差异：${detected.base} → ${detected.obs} · ${detected.changes_total} 项待复核`
                    : "接入真实后端后，快照差异引擎自动检出岗位技能变化草稿"}
                </span>
              </div>
            </header>
            {detected ? (
              <ul className="detected-list">
                {detected.jobs.slice(0, 6).map((job) => (
                  <li className="detected-item" key={job.position_id}>
                    <div>
                      <strong>{job.job}</strong>
                      <small>
                        {job.base_jds} → {job.obs_jds} 条 JD ·{" "}
                        {job.changes.length} 项变化
                      </small>
                    </div>
                    <div className="training-tags">
                      {job.changes.slice(0, 3).map((ch) => (
                        <span
                          className={`detected-tag detected-${ch.change_type}`}
                          key={ch.skill_id}
                        >
                          {`${ch.name} ${Math.round(ch.base_share * 100)}%→${Math.round(
                            ch.obs_share * 100,
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
