"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { ArrowSquareOut } from "@phosphor-icons/react";
import {
  Button,
  Descriptions,
  Drawer,
  Empty,
  Input,
  Progress,
  Select,
  Tag,
} from "antd";

import { SectionHeader } from "@/components/workflow-ui";
import type { TrendSignal } from "@/lib/temporal";
import { skillDisplay } from "@/lib/skill-labels";
import type { Evidence } from "@/lib/job-update";
import { apiFetch } from "@/lib/api/client";

const TYPE_LABEL: Record<TrendSignal["signal_type"], string> = {
  mention: "提及",
  adoption: "采用",
  job_requirement: "岗位需求",
  release: "发布",
  policy: "政策",
};

function signalTime(value: string): { date: string; time: string } {
  const date = new Date(value);
  return {
    date: new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(date),
    time: new Intl.DateTimeFormat("zh-CN", {
      timeZone: "Asia/Shanghai",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    }).format(date),
  };
}

export function TemporalSignalsWorkbench({
  signals,
}: {
  signals: TrendSignal[];
}) {
  const [visibleCount, setVisibleCount] = useState(50);
  const [query, setQuery] = useState("");
  const [signalType, setSignalType] = useState<
    "all" | TrendSignal["signal_type"]
  >("all");
  const [skillId, setSkillId] = useState("all");
  const [selected, setSelected] = useState<TrendSignal | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [evidenceLoading, setEvidenceLoading] = useState(false);
  const loadMoreRef = useRef<HTMLDivElement>(null);

  const latest = useMemo(
    () => signals.reduce((m, s) => (s.observed_at > m ? s.observed_at : m), ""),
    [signals],
  );
  const clusters = useMemo(() => {
    const groups = new Map<string, number>();
    for (const s of signals) {
      groups.set(
        s.canonical_skill_id,
        (groups.get(s.canonical_skill_id) ?? 0) + 1,
      );
    }
    return [...groups.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([skill, count]) => ({ skill, count }));
  }, [signals]);
  const filteredSignals = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("zh-CN");
    return signals.filter((signal) => {
      if (signalType !== "all" && signal.signal_type !== signalType)
        return false;
      if (skillId !== "all" && signal.canonical_skill_id !== skillId)
        return false;
      if (!needle) return true;
      return `${skillDisplay(signal.canonical_skill_id)} ${signal.evidence_span}`
        .toLocaleLowerCase("zh-CN")
        .includes(needle);
    });
  }, [query, signalType, signals, skillId]);

  useEffect(() => {
    const target = loadMoreRef.current;
    const root = target?.closest(".temporal-workbench");
    if (!target || !root || visibleCount >= filteredSignals.length) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisibleCount((count) =>
            Math.min(count + 50, filteredSignals.length),
          );
        }
      },
      { root, rootMargin: "0px 0px 240px 0px" },
    );
    observer.observe(target);
    return () => observer.disconnect();
  }, [filteredSignals.length, visibleCount]);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    Promise.all(
      selected.evidence_ids.map((id) =>
        apiFetch<Evidence>(`/evidence/${encodeURIComponent(id)}`).catch(
          () => null,
        ),
      ),
    ).then((items) => {
      if (cancelled) return;
      setEvidence(items.filter((item): item is Evidence => item !== null));
      setEvidenceLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [selected]);

  return (
    <section className="temporal-workbench" aria-label="市场信号">
      <div className="temporal-signal-toolbar">
        <div>
          <strong>{`${filteredSignals.length} 条信号`}</strong>
          <span>{latest ? `最近更新 ${latest.slice(0, 10)}` : "暂无更新"}</span>
        </div>
        <Input
          allowClear
          aria-label="搜索市场信号"
          onChange={(event) => {
            setQuery(event.target.value);
            setVisibleCount(50);
          }}
          placeholder="搜索能力域或信号内容"
          value={query}
        />
        <Select
          aria-label="筛选信号类型"
          onChange={(value) => {
            setSignalType(value);
            setVisibleCount(50);
          }}
          options={[
            { label: "全部类型", value: "all" },
            ...Object.entries(TYPE_LABEL).map(([value, label]) => ({
              label,
              value,
            })),
          ]}
          value={signalType}
        />
      </div>
      <div className="temporal-signal-layout">
        <section className="temporal-signal-timeline" aria-label="信号时间线">
          <SectionHeader
            meta={`已显示 ${Math.min(visibleCount, filteredSignals.length)} / ${filteredSignals.length} 条`}
            title="信号流"
          />
          <ol className="temporal-event-timeline">
            {filteredSignals.slice(0, visibleCount).map((s, index) => {
              const observed = signalTime(s.observed_at);
              return (
                <li key={`${s.signal_id}-${s.observed_at}-${index}`}>
                  <time dateTime={s.observed_at}>
                    <strong>{observed.date}</strong>
                    <span>{observed.time}</span>
                  </time>
                  <span
                    aria-hidden
                    className={`temporal-event-node type-${s.signal_type}`}
                  />
                  <article>
                    <div className="temporal-event-heading">
                      <strong>{skillDisplay(s.canonical_skill_id)}</strong>
                      <Tag>{TYPE_LABEL[s.signal_type]}</Tag>
                      <span>{`置信度 ${(s.confidence * 100).toFixed(0)}%`}</span>
                      <Button
                        onClick={() => {
                          setEvidence([]);
                          setEvidenceLoading(true);
                          setSelected(s);
                        }}
                        size="small"
                        type="link"
                      >
                        查看来源
                      </Button>
                    </div>
                    <p>{s.evidence_span}</p>
                  </article>
                </li>
              );
            })}
          </ol>
          <div
            aria-live="polite"
            className="temporal-load-sentinel"
            ref={loadMoreRef}
          >
            {visibleCount < filteredSignals.length
              ? "继续向下滚动加载更多"
              : filteredSignals.length > 0
                ? `已显示全部 ${filteredSignals.length} 条`
                : "没有符合条件的信号"}
          </div>
        </section>

        <aside className="temporal-signal-clusters" aria-label="信号簇">
          <SectionHeader meta="点击筛选" title="高频能力域" />
          <ul>
            <li>
              <button
                aria-pressed={skillId === "all"}
                className={skillId === "all" ? "is-active" : ""}
                onClick={() => {
                  setSkillId("all");
                  setVisibleCount(50);
                }}
                type="button"
              >
                <span>全部能力域</span>
                <span>{signals.length} 条</span>
              </button>
            </li>
            {clusters.map((c) => (
              <li key={c.skill}>
                <button
                  aria-pressed={skillId === c.skill}
                  className={skillId === c.skill ? "is-active" : ""}
                  onClick={() => {
                    setSkillId(c.skill);
                    setVisibleCount(50);
                  }}
                  type="button"
                >
                  <span className="temporal-signal-cluster-skill">
                    {skillDisplay(c.skill)}
                  </span>
                  <span className="temporal-signal-cluster-count">
                    {c.count} 条
                  </span>
                </button>
              </li>
            ))}
            {clusters.length === 0 ? (
              <li className="temporal-empty">无信号</li>
            ) : null}
          </ul>
        </aside>
      </div>
      <Drawer
        onClose={() => {
          setSelected(null);
          setEvidence([]);
          setEvidenceLoading(false);
        }}
        open={selected !== null}
        size="large"
        title={
          selected
            ? `${skillDisplay(selected.canonical_skill_id)}的来源`
            : "信号来源"
        }
      >
        {selected ? (
          <div className="temporal-signal-evidence">
            <p>{selected.evidence_span}</p>
            <Descriptions bordered column={1} size="small">
              <Descriptions.Item label="信号类型">
                {TYPE_LABEL[selected.signal_type]}
              </Descriptions.Item>
              <Descriptions.Item label="观察时间">
                {selected.observed_at}
              </Descriptions.Item>
              <Descriptions.Item label="能力映射">
                {skillDisplay(selected.canonical_skill_id)}
              </Descriptions.Item>
              <Descriptions.Item label="信号 ID">
                {selected.signal_id}
              </Descriptions.Item>
            </Descriptions>
            {evidenceLoading ? <p>正在读取来源...</p> : null}
            {!evidenceLoading && evidence.length === 0 ? (
              <Empty description="证据记录暂无可展示的来源详情" />
            ) : null}
            {evidence.map((item) => (
              <article className="temporal-signal-evidence-item" key={item.id}>
                <div>
                  <Tag>{item.sourceType}</Tag>
                  <strong>{item.source}</strong>
                  <span>{item.publishedAt}</span>
                </div>
                <p>{item.excerpt}</p>
                <Progress
                  percent={Math.round(item.quality * 100)}
                  size="small"
                />
                <small>{`证据 ID：${item.id}`}</small>
                {item.sourceUrl ? (
                  <Button
                    href={item.sourceUrl}
                    icon={<ArrowSquareOut aria-hidden />}
                    target="_blank"
                    type="link"
                  >
                    打开原始来源
                  </Button>
                ) : (
                  <span className="temporal-source-unavailable">
                    原始来源未保存外部链接
                  </span>
                )}
              </article>
            ))}
          </div>
        ) : null}
      </Drawer>
    </section>
  );
}
