import Link from "next/link";
import {
  ClipboardText,
  GitDiff,
  MagnifyingGlass,
  ShieldCheck,
} from "@phosphor-icons/react";

import { AppShell } from "@/components/app-shell";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DashboardOverview } from "@/lib/dashboard";

const dashboardIcons = [MagnifyingGlass, GitDiff, ClipboardText];
const dashboardCounts = [
  {
    href: "/new-jobs",
    icon: MagnifyingGlass,
    label: "新岗位待审",
    value: "5",
    meta: "3 家企业 · 8 条来源",
  },
  {
    href: "/jobs",
    icon: GitDiff,
    label: "岗位更新待审",
    value: "6",
    meta: "v1.4 → v1.5 · 22 样本",
  },
  {
    href: "/diagnosis",
    icon: ClipboardText,
    label: "诊断中",
    value: "2",
    meta: "1 高优 · 1 待画像",
  },
  {
    href: "/evaluation",
    icon: ShieldCheck,
    label: "今日回测",
    value: "3",
    meta: "命中率 0.61 · 待复盘 1",
  },
];

const temporalEntry = {
  href: "/temporal",
  label: "时间情报",
  value: "4",
  meta: "信号流 / 趋势回测 / 预测复盘 / 影响建议",
};

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
  const queue = dashboard?.queue ?? dashboardCounts.slice(0, 3).map(({ href, label, value, meta }) => ({ href, label, value: Number(value), meta }));
  return (
    <AppShell>
      <section className="dashboard" aria-labelledby="dashboard-title">
        <header className="page-heading">
          <h1 id="dashboard-title">工作台</h1>
          <p>
            今天从待处理事项开始，沿证据、审核到岗位版本完成闭环。
          </p>
        </header>
        <div className="dashboard-focus-layout">
          <section className="dashboard-focus" aria-labelledby="focus-title">
            <div className="dashboard-section-heading">
              <div>
                <span className="dashboard-kicker">下一步</span>
                <h2 id="focus-title">处理 {focus.title} 更新审核</h2>
              </div>
              <span className="dashboard-focus-status">{focus.pending} 条待审核</span>
            </div>
            <p>
              {focus.summary}先查看证据，再决定是否进入新版本。
            </p>
            <Link className="dashboard-primary-action" href={focus.href}>
              <GitDiff aria-hidden size={18} />
              打开岗位更新
            </Link>
          </section>
          <aside className="dashboard-status" aria-label="运行状态">
            <div className="dashboard-section-heading">
              <h2>运行状态</h2>
              <span className="dashboard-status-live">正常</span>
            </div>
            <dl>
              <div><dt>数据截至</dt><dd>{dashboard?.status.data_as_of ?? "08-22"}</dd></div>
              <div><dt>今日回测</dt><dd>{dashboard?.status.backtests ?? "3"} 个运行</dd></div>
              <div><dt>待审核</dt><dd>{dashboard?.status.pending_reviews ?? focus.pending} 项</dd></div>
            </dl>
          </aside>
        </div>
        <section className="dashboard-queue" aria-labelledby="queue-title">
          <div className="dashboard-section-heading">
            <div>
              <span className="dashboard-kicker">工作队列</span>
              <h2 id="queue-title">需要你决定的事项</h2>
            </div>
            <Link href="/tasks">查看全部任务</Link>
          </div>
          <ul className="dashboard-queue-grid">
            {queue.map(({ href, label, value, meta }, index) => { const Icon = dashboardIcons[index] ?? ClipboardText; return (
              <li key={href}>
                <Link className="dashboard-queue-item" href={href}>
                  <Icon aria-hidden size={18} />
                  <span><strong>{label}</strong><small>{meta}</small></span>
                  <b>{value}</b>
                </Link>
              </li>
            ); })}
          </ul>
        </section>
        <Link className="dashboard-secondary-link" href={temporalEntry.href}>
          <span><strong>{temporalEntry.label}</strong><small>{temporalEntry.meta}</small></span>
          <b>进入时间情报 →</b>
        </Link>
      </section>
    </AppShell>
  );
}
