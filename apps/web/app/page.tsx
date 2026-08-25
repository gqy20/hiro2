"use client";

import Link from "next/link";
import {
  ClipboardText,
  GitDiff,
  MagnifyingGlass,
  ShieldCheck,
} from "@phosphor-icons/react";

import { AppShell } from "@/components/app-shell";

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

export default function DashboardPage() {
  return (
    <AppShell>
      <section className="dashboard" aria-labelledby="dashboard-title">
        <header className="page-heading">
          <h1 id="dashboard-title">工作台</h1>
          <p>
            Hiro2 的入口。四个数字对应一级导航的核心模块，演示数据来自当前 fixture 快照。
          </p>
        </header>
        <ul className="dashboard-grid">
          {dashboardCounts.map(({ href, icon: Icon, label, value, meta }) => (
            <li key={href}>
              <Link className="dashboard-card" href={href}>
                <Icon aria-hidden size={20} />
                <span className="dashboard-card-label">{label}</span>
                <strong className="dashboard-card-value">{value}</strong>
                <span className="dashboard-card-meta">{meta}</span>
              </Link>
            </li>
          ))}
        </ul>
        <Link className="dashboard-temporal-card" href={temporalEntry.href}>
          <span className="dashboard-card-label">{temporalEntry.label}</span>
          <strong className="dashboard-card-value">
            {temporalEntry.value} 个次级视图
          </strong>
          <span className="dashboard-card-meta">{temporalEntry.meta}</span>
        </Link>
      </section>
    </AppShell>
  );
}