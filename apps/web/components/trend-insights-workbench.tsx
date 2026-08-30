"use client";

import { useMemo, useState } from "react";
import { Button, Select, Tag } from "antd";

import { allSkillOptions, skillLabel } from "@/lib/skill-labels";
import type {
  BacktestRecord,
  ForecastResult,
  JobImpactSuggestion,
  TemporalTimeline,
  TrendSignal,
} from "@/lib/temporal";

const RANGE_OPTIONS = [
  { label: "近 30 天", value: "30" },
  { label: "近 90 天", value: "90" },
  { label: "近 1 年", value: "365" },
  { label: "全部时间", value: "all" },
] as const;

const TYPE_LABEL: Record<string, string> = {
  mention: "提及",
  adoption: "采用",
  job_requirement: "岗位需求",
  release: "发布",
  policy: "政策",
};

function directionLabel(direction: string): string {
  if (direction === "up") return "持续上升";
  if (direction === "down") return "持续下降";
  return "保持平稳";
}

type RankingItem = { id: string; label: string; count: number };
type Milestone = {
  key: "paper" | "package" | "report" | "job";
  label: string;
  date: string;
};

function confidenceMeta(confidence: number): { label: string; color: string } {
  if (confidence >= 0.75) return { label: "高置信度", color: "green" };
  if (confidence >= 0.5) return { label: "中置信度", color: "gold" };
  return { label: "低置信度", color: "orange" };
}

function monthIndex(value: string): number {
  const [year, month] = value.split("-").map(Number);
  return year * 12 + month;
}

function impactReason(value: string): string {
  const preceded = value.match(/信号领先\s*-(\d+)\s*天（jd_preceded）/);
  if (preceded) {
    return `岗位需求早于当前信号锚点 ${preceded[1]} 天，建议复核是否属于存量能力。`;
  }
  return value.replace(/\s*\([^)]*\)\s*$/, "");
}

export function TrendInsightsWorkbench({
  signals,
  forecasts,
  backtestRecords,
  suggestions,
  timeline,
  jobLabels,
}: {
  signals: TrendSignal[];
  forecasts: ForecastResult[];
  backtestRecords: BacktestRecord[];
  suggestions: JobImpactSuggestion[];
  timeline: TemporalTimeline;
  jobLabels: Record<string, string>;
}) {
  const latest = signals[0]?.observed_at ?? "";
  const [range, setRange] =
    useState<(typeof RANGE_OPTIONS)[number]["value"]>("90");
  const [skillId, setSkillId] = useState(
    forecasts.find((item) => item.skill_id === "cap_04")?.skill_id ??
      forecasts[0]?.skill_id ??
      signals[0]?.canonical_skill_id ??
      "",
  );

  const rangedSignals = useMemo(() => {
    if (range === "all" || !latest) return signals;
    const cutoff = Date.parse(latest) - Number(range) * 24 * 60 * 60 * 1000;
    return signals.filter((signal) => Date.parse(signal.observed_at) >= cutoff);
  }, [latest, range, signals]);
  const ranking = useMemo<RankingItem[]>(() => {
    const counts = new Map<string, number>();
    for (const signal of rangedSignals) {
      counts.set(
        signal.canonical_skill_id,
        (counts.get(signal.canonical_skill_id) ?? 0) + 1,
      );
    }
    const known = new Set<string>();
    const items = allSkillOptions().map(({ id, label }) => {
      known.add(id);
      return { id, label, count: counts.get(id) ?? 0 };
    });
    for (const [id, count] of counts) {
      if (!known.has(id)) items.push({ id, label: skillLabel(id), count });
    }
    return items.sort(
      (a, b) => b.count - a.count || a.label.localeCompare(b.label, "zh-CN"),
    );
  }, [rangedSignals]);
  const skillSignals = rangedSignals.filter(
    (signal) => signal.canonical_skill_id === skillId,
  );
  const selectedSignals = skillSignals.slice(0, 8);
  const forecast = forecasts.find((item) => item.skill_id === skillId);
  const record = backtestRecords
    .filter((item) => item.skill_id === skillId)
    .sort((a, b) => b.rule_version - a.rule_version)[0];
  const transmission = timeline.rows.find(
    (item) => item.capability_id === skillId,
  );
  const impacts = suggestions.filter((item) => item.skill_id === skillId);
  const confidence = forecast?.confidence ?? record?.confidence ?? 0;
  const hasForecast = Boolean(forecast || record);
  const direction =
    forecast?.predicted_direction ?? record?.predicted ?? "flat";
  const rangeLabel =
    RANGE_OPTIONS.find((item) => item.value === range)?.label ?? "当前范围";
  const confidenceState = confidenceMeta(confidence);
  const milestones = useMemo<Milestone[]>(() => {
    if (!transmission) return [];
    return [
      { key: "paper", label: "论文首次出现", date: transmission.arxiv_onset },
      {
        key: "package",
        label: "生态包形成规模",
        date: transmission.pypi_onset ?? transmission.npm_onset,
      },
      {
        key: "report",
        label: "行业传播形成规模",
        date: transmission.report_onset,
      },
      { key: "job", label: "岗位需求出现", date: transmission.jd_onset },
    ]
      .filter((item): item is Milestone => Boolean(item.date))
      .sort((a, b) => a.date.localeCompare(b.date));
  }, [transmission]);
  const transmissionSummary = useMemo(() => {
    if (!transmission?.arxiv_onset || !transmission.jd_onset) {
      return "论文与岗位的时间关系尚不完整。";
    }
    const paperToJob =
      monthIndex(transmission.jd_onset) - monthIndex(transmission.arxiv_onset);
    const parts = [
      paperToJob >= 0
        ? `论文先行，岗位需求在 ${paperToJob} 个月后出现`
        : `岗位需求早于论文 ${Math.abs(paperToJob)} 个月`,
    ];
    const packageDate = transmission.pypi_onset ?? transmission.npm_onset;
    if (packageDate) {
      const jobToPackage =
        monthIndex(packageDate) - monthIndex(transmission.jd_onset);
      if (jobToPackage > 0)
        parts.push(`岗位需求早于生态包规模化 ${jobToPackage} 个月`);
      if (jobToPackage < 0)
        parts.push(`生态包规模化早于岗位需求 ${Math.abs(jobToPackage)} 个月`);
    }
    return `${parts.join("；")}。`;
  }, [transmission]);
  return (
    <section className="trend-insights" aria-labelledby="trend-insights-title">
      <header className="trend-insights-toolbar">
        <div>
          <h1 id="trend-insights-title" className="sr-only">
            趋势洞察
          </h1>
          <strong>{skillLabel(skillId)}</strong>
        </div>
        <label className="trend-range-control">
          <span>信号范围</span>
          <Select
            aria-label="筛选信号时间范围"
            onChange={setRange}
            options={[...RANGE_OPTIONS]}
            value={range}
          />
        </label>
      </header>

      <div className="trend-insights-layout">
        <aside className="trend-ranking" aria-label="能力域趋势排行">
          <div className="trend-section-heading">
            <h2>
              {`${ranking.length} 个能力域`}
              <span>{` · ${rangedSignals.length.toLocaleString("zh-CN")} 条信号`}</span>
            </h2>
          </div>
          <ol>
            {ranking.map((item, index) => (
              <li
                className={item.count === 0 ? "has-no-signal" : ""}
                key={item.id}
              >
                <button
                  aria-pressed={skillId === item.id}
                  className={skillId === item.id ? "is-active" : ""}
                  onClick={() => setSkillId(item.id)}
                  type="button"
                >
                  <span>{index + 1}</span>
                  <strong>{item.label}</strong>
                  <em>{item.count}</em>
                </button>
              </li>
            ))}
          </ol>
        </aside>

        <main className="trend-detail">
          <section className="trend-decision">
            <div className="trend-decision-heading">
              <div>
                <span>当前判断</span>
                <strong>
                  {hasForecast ? directionLabel(direction) : "暂无预测"}
                </strong>
              </div>
              {hasForecast ? (
                <Tag color={confidenceState.color}>
                  {`${confidenceState.label} · ${Math.round(confidence * 100)}%`}
                </Tag>
              ) : null}
            </div>
            <div className="trend-decision-meta">
              <span>{rangeLabel}</span>
              <span>
                <strong>{skillSignals.length.toLocaleString("zh-CN")}</strong>{" "}
                条信号
              </span>
              <span>
                <strong>{impacts.length}</strong> 条岗位影响
              </span>
              <span>
                截至 <time>{latest ? latest.slice(0, 10) : "—"}</time>
              </span>
            </div>
          </section>

          <section className="trend-transmission">
            <div className="trend-section-heading">
              <h2>技术传导</h2>
              <span>
                {transmission?.paper_to_jd_months == null
                  ? "完整历史 · 链路待补充"
                  : `完整历史 · 论文 → 岗位 ${Math.abs(transmission.paper_to_jd_months)} 个月`}
              </span>
            </div>
            {milestones.length ? (
              <div className="trend-milestones" aria-label="技术演化时间轴">
                {milestones.map((milestone) => (
                  <div className={`is-${milestone.key}`} key={milestone.key}>
                    <time>{milestone.date}</time>
                    <span aria-hidden />
                    <strong>{milestone.label}</strong>
                  </div>
                ))}
              </div>
            ) : (
              <p className="trend-empty">当前能力域暂无完整传导数据。</p>
            )}
            <p className="trend-relation-summary">{transmissionSummary}</p>
            <details className="trend-methodology">
              <summary>查看计算口径</summary>
              <p>{timeline.note.replace(/\bonset\b/gi, "起始月")}</p>
              {transmission ? (
                <div>
                  <span>{`论文：${transmission.arxiv_onset ?? "未达到阈值"}`}</span>
                  <span>{`生态包：${transmission.pypi_onset ?? transmission.npm_onset ?? "未达到阈值"}`}</span>
                  <span>{`行业传播：${transmission.report_onset ?? "未达到阈值"}`}</span>
                  <span>{`岗位需求：${transmission.jd_onset ?? "未达到阈值"}`}</span>
                </div>
              ) : null}
            </details>
          </section>

          <section className="trend-recent-signals">
            <div className="trend-section-heading">
              <h2>近期依据</h2>
              <Button
                href="/tasks?view=evidence&source_id=wechat-mp"
                type="link"
              >
                查看全部信号
              </Button>
            </div>
            <ol>
              {selectedSignals.map((signal, index) => (
                <li key={`${signal.signal_id}-${signal.observed_at}-${index}`}>
                  <time>{signal.observed_at.slice(0, 10)}</time>
                  <Tag>
                    {TYPE_LABEL[signal.signal_type] ?? signal.signal_type}
                  </Tag>
                  <p>{signal.evidence_span}</p>
                </li>
              ))}
            </ol>
            {selectedSignals.length === 0 ? (
              <p className="trend-empty">当前时间范围内暂无该能力域信号。</p>
            ) : null}
          </section>
        </main>

        <aside className="trend-impacts" aria-label="岗位影响">
          <div className="trend-section-heading">
            <h2>岗位影响</h2>
            <span>{`${impacts.length} 条建议`}</span>
          </div>
          {impacts.length ? (
            <ul>
              {impacts.map((impact) => (
                <li key={impact.suggestion_id}>
                  <Tag>
                    {impact.review_status === "PENDING"
                      ? "待审核"
                      : impact.review_status}
                  </Tag>
                  <strong>{jobLabels[impact.job_id] ?? "待关联岗位"}</strong>
                  <p>{impactReason(impact.reason)}</p>
                </li>
              ))}
            </ul>
          ) : (
            <p className="trend-empty">当前能力域暂无岗位影响建议。</p>
          )}
          <Button block href="/tasks?view=tasks" type="primary">
            进入审核任务
          </Button>
          <Button block href="/evaluation">
            查看预测质量
          </Button>
        </aside>
      </div>
    </section>
  );
}
