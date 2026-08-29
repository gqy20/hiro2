"use client";

import { useMemo, useState } from "react";
import { Segmented } from "antd";

import type { TemporalTimeline, TemporalTimelineRow } from "@/lib/temporal";

type TimelineFilter = "all" | "paper-first" | "job-first" | "incomplete";
type TimelineRelation = Exclude<TimelineFilter, "all">;

function relation(row: TemporalTimelineRow): TimelineRelation {
  if (row.paper_to_jd_months === null) return "incomplete";
  return row.paper_to_jd_months >= 0 ? "paper-first" : "job-first";
}

function relationLabel(months: number | null): string {
  if (months === null) return "链路不完整";
  if (months > 0) return `论文领先岗位 ${months} 个月`;
  if (months < 0) return `岗位早于论文 ${Math.abs(months)} 个月`;
  return "论文与岗位同月出现";
}

function packageLabel(row: TemporalTimelineRow): string {
  const values = [
    row.pypi_onset ? `PyPI ${row.pypi_onset}` : "",
    row.npm_onset ? `npm ${row.npm_onset}` : "",
  ].filter(Boolean);
  return values.join(" / ") || "未达到阈值";
}

export function TemporalTimelineWorkbench({
  data,
}: {
  data: TemporalTimeline;
}) {
  const [filter, setFilter] = useState<TimelineFilter>("all");
  const counts = useMemo(
    () =>
      data.rows.reduce(
        (result, row) => {
          result[relation(row)] += 1;
          return result;
        },
        { "paper-first": 0, "job-first": 0, incomplete: 0 },
      ),
    [data.rows],
  );
  const rows = data.rows.filter(
    (row) => filter === "all" || relation(row) === filter,
  );

  return (
    <section
      className="temporal-workbench temporal-timeline-workbench"
      aria-label="技术传导"
    >
      <div className="temporal-transmission-summary">
        <div>
          <strong>{data.rows.length}</strong>
          <span>个能力域</span>
        </div>
        <div>
          <strong>{counts["paper-first"]}</strong>
          <span>论文先行</span>
        </div>
        <div>
          <strong>{counts["job-first"]}</strong>
          <span>岗位先行</span>
        </div>
        <div>
          <strong>{counts.incomplete}</strong>
          <span>链路不完整</span>
        </div>
        <p>{data.note.replace("onset", "起始月")}</p>
      </div>

      <div className="temporal-transmission-toolbar">
        <div>
          <h2>能力传导路径</h2>
          <p>比较技术首次形成规模与岗位需求出现的先后关系。</p>
        </div>
        <Segmented
          aria-label="筛选传导关系"
          onChange={(value) => setFilter(value as TimelineFilter)}
          options={[
            { label: "全部", value: "all" },
            { label: "论文先行", value: "paper-first" },
            { label: "岗位先行", value: "job-first" },
            { label: "信息不全", value: "incomplete" },
          ]}
          value={filter}
        />
      </div>

      <div className="temporal-transmission-head" aria-hidden="true">
        <span>能力域</span>
        <span>论文</span>
        <span>生态包</span>
        <span>媒体</span>
        <span>岗位</span>
        <span>时间关系</span>
      </div>
      <ol className="temporal-transmission-list">
        {rows.map((row) => {
          const rowRelation = relation(row);
          return (
            <li className={`is-${rowRelation}`} key={row.capability_id}>
              <strong>{row.name}</strong>
              <div className="temporal-transmission-stage">
                <small>论文</small>
                <span>{row.arxiv_onset ?? "未达到阈值"}</span>
              </div>
              <div className="temporal-transmission-stage">
                <small>生态包</small>
                <span>{packageLabel(row)}</span>
              </div>
              <div className="temporal-transmission-stage">
                <small>媒体</small>
                <span>{row.report_onset ?? "未达到阈值"}</span>
              </div>
              <div className="temporal-transmission-stage">
                <small>岗位</small>
                <span>{row.jd_onset ?? "未达到阈值"}</span>
              </div>
              <em>{relationLabel(row.paper_to_jd_months)}</em>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
