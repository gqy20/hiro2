"use client";

import { useMemo, useState } from "react";
import { Timeline, Tooltip } from "antd";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/workflow-ui";
import { TemporalNav } from "@/components/temporal-nav";
import type { TrendSignal, TrendSignalEntityType } from "@/lib/temporal";

const ENTITY_LABEL: Record<TrendSignalEntityType, string> = {
  skill: "技能",
  technology: "技术",
  industry: "行业",
  job: "岗位",
};

const TYPE_LABEL: Record<TrendSignal["signal_type"], string> = {
  mention: "提及",
  adoption: "采用",
  job_requirement: "岗位需求",
  release: "发布",
  policy: "政策",
};

const WINDOWS = [
  { days: 7, label: "近 7 天" },
  { days: 30, label: "近 30 天" },
  { days: 90, label: "近 90 天" },
];

function startOfToday(): Date {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
}

export function TemporalSignalsWorkbench({
  signals,
}: {
  signals: TrendSignal[];
}) {
  const [days, setDays] = useState(30);

  const filtered = useMemo(() => {
    const cutoff = startOfToday();
    cutoff.setDate(cutoff.getDate() - days);
    const cutoffStr = cutoff.toISOString().slice(0, 10);
    return signals.filter((s) => s.observed_at >= cutoffStr);
  }, [signals, days]);

  const clusters = useMemo(() => {
    const groups = new Map<string, number>();
    for (const s of filtered) {
      groups.set(
        s.canonical_skill_id,
        (groups.get(s.canonical_skill_id) ?? 0) + 1,
      );
    }
    return [...groups.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([skill, count]) => ({ skill, count }));
  }, [filtered]);

  return (
    <AppShell>
      <section
        className="temporal-workbench"
        aria-labelledby="signals-title"
      >
        <header className="page-heading">
          <h1 id="signals-title">信号流 + 信号簇</h1>
          <p>{`${filtered.length} / ${signals.length} 条信号在选定时间窗内`}</p>
        </header>
        <TemporalNav />

        <div className="temporal-filters">
          {WINDOWS.map((w) => (
            <button
              aria-pressed={w.days === days}
              className={`temporal-filter-tab ${
                w.days === days ? "is-active" : ""
              }`}
              key={w.days}
              onClick={() => setDays(w.days)}
              type="button"
            >
              {w.label}
            </button>
          ))}
        </div>

        <div className="temporal-signal-layout">
          <section
            className="temporal-signal-timeline"
            aria-label="信号时间线"
          >
            <SectionHeader meta={`${filtered.length} 条`} title="按时间倒序" />
            <Timeline
              items={filtered.slice(0, 20).map((s) => ({
                color:
                  s.signal_type === "policy"
                    ? "red"
                    : s.signal_type === "release"
                      ? "blue"
                      : s.signal_type === "adoption"
                        ? "green"
                        : "gray",
                children: (
                  <div>
                    <strong>{s.canonical_skill_id}</strong>
                    <p>
                      <Tooltip title={s.evidence_span}>
                        {s.evidence_span}
                      </Tooltip>
                    </p>
                    <small>
                      {`${s.observed_at} · ${ENTITY_LABEL[s.entity_type]} · ${TYPE_LABEL[s.signal_type]} · 置信 ${(s.confidence * 100).toFixed(0)}%`}
                    </small>
                  </div>
                ),
              }))}
            />
          </section>

          <aside className="temporal-signal-clusters" aria-label="信号簇">
            <SectionHeader meta="Top 5" title="按技能聚类" />
            <ul>
              {clusters.map((c) => (
                <li key={c.skill}>
                  <span className="temporal-signal-cluster-skill">
                    {c.skill}
                  </span>
                  <span className="temporal-signal-cluster-count">
                    {c.count} 条
                  </span>
                </li>
              ))}
              {clusters.length === 0 ? (
                <li className="temporal-empty">无信号</li>
              ) : null}
            </ul>
          </aside>
        </div>
      </section>
    </AppShell>
  );
}