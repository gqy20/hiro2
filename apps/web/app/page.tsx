import Link from "next/link";
import { AppShell } from "@/components/app-shell";
import { DashboardIcon } from "@/components/dashboard-icons";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DashboardOverview } from "@/lib/dashboard";
import { DashboardTrend } from "@/components/dashboard-trend";

export default async function DashboardPage() {
  const dashboard = isMockMode()
    ? null
    : await apiFetch<DashboardOverview>("/dashboard/overview");
  const focus = dashboard?.focus ?? {
    title: "AI 应用工程师（综合）",
    stage: "审核能力变化",
    next: "完成审核后发布新版本",
    href: "/jobs",
    pending: "13",
    summary: "13 项能力变化，来自 73 条样本。",
  };
  const jobs = dashboard?.jobs ?? [
    {
      title: focus.title,
      version: "v1.5",
      status: "待审核",
      pending: Number(focus.pending),
      href: "/jobs",
    },
  ];
  const metrics = dashboard?.metrics ?? {
    positions: 1,
    needs_update: 1,
    pending_changes: Number(focus.pending),
    published_versions: 1,
  };
  const attention = dashboard?.attention ?? [
    {
      title: focus.title,
      detail: `${focus.pending} 项能力变化待审核`,
      href: "/jobs",
    },
  ];
  return (
    <AppShell>
      <section className="dashboard" aria-labelledby="dashboard-title">
        <header className="page-heading">
          <div className="dashboard-title-row">
            <div>
              <h1 id="dashboard-title">工作台</h1>
            </div>
            <div className="dashboard-title-meta">
              <span className="dashboard-space-label">招聘工作区</span>
              <div
                className="dashboard-title-metrics"
                aria-label="岗位总体状态"
              >
                <span>
                  <strong>{metrics.positions}</strong>
                  <small>负责岗位</small>
                </span>
                <span>
                  <strong>{metrics.needs_update}</strong>
                  <small>需要更新</small>
                </span>
                <span>
                  <strong>{metrics.pending_changes}</strong>
                  <small>待审核变化</small>
                </span>
                <span>
                  <strong>{metrics.published_versions}</strong>
                  <small>已发布版本</small>
                </span>
              </div>
            </div>
          </div>
        </header>
        <div className="dashboard-focus-layout">
          <Link
            className="dashboard-focus"
            href={focus.href}
            aria-labelledby="focus-title"
          >
            <div className="dashboard-section-heading">
              <div>
                <h2 id="focus-title">{focus.title}</h2>
              </div>
              <span className="dashboard-focus-status">
                {focus.pending} 条待审核
              </span>
            </div>
            <p>{focus.summary}</p>
            <span className="dashboard-focus-hint">
              <DashboardIcon kind="diff" />
              查看岗位 →
            </span>
          </Link>
          <aside className="dashboard-status" aria-label="运行状态">
            <div className="dashboard-section-heading">
              <h2>运行状态</h2>
              <span className="dashboard-status-live">正常</span>
            </div>
            <dl>
              <div>
                <dt>数据截至</dt>
                <dd>{dashboard?.status.data_as_of ?? "08-22"}</dd>
              </div>
              <div>
                <dt>今日回测</dt>
                <dd>{dashboard?.status.backtests ?? "3"} 个运行</dd>
              </div>
              <div>
                <dt>待审核</dt>
                <dd>{dashboard?.status.pending_reviews ?? focus.pending} 项</dd>
              </div>
            </dl>
          </aside>
        </div>
        <div className="dashboard-insights-grid">
          <section className="dashboard-trend" aria-labelledby="trend-title">
            <div className="dashboard-section-heading">
              <div className="dashboard-heading-inline">
                <h2 id="trend-title">能力需求趋势</h2>
                <span>近期开启岗位中的能力提及变化</span>
              </div>
              <span className="dashboard-trend-range">
                {dashboard?.trends?.[0]?.months.at(0) ?? "2025-09"} 至{" "}
                {dashboard?.trends?.[0]?.months.at(-1) ?? "2026-08"} · JD
                月度提及率
              </span>
            </div>
            <DashboardTrend trends={dashboard?.trends ?? []} />
          </section>
          <section
            className="dashboard-attention"
            aria-labelledby="attention-title"
          >
            <div className="dashboard-section-heading">
              <div>
                <h2 id="attention-title">需要关注</h2>
              </div>
            </div>
            <ul>
              {attention.map((item) => (
                <li key={item.href}>
                  <Link href={item.href}>
                    <strong>{item.title}</strong>
                    <span>{item.detail}</span>
                    <b>查看 →</b>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </div>
        <section className="dashboard-jobs" aria-labelledby="jobs-title">
          <div className="dashboard-section-heading">
            <div>
              <h2 id="jobs-title">我的岗位</h2>
            </div>
            <span className="dashboard-section-link">岗位列表 →</span>
          </div>
          {jobs.map((job) => (
            <Link
              className="dashboard-job-row"
              href="/positions"
              key={job.href}
            >
              <span>
                <strong>{job.title}</strong>
                <small>
                  当前版本 {job.version} · {job.status}
                </small>
              </span>
              <em>{job.pending} 项变化待审核</em>
              <b>继续审核 →</b>
            </Link>
          ))}
        </section>
      </section>
    </AppShell>
  );
}
