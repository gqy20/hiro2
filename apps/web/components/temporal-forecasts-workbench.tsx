"use client";

import { useMemo, useState } from "react";
import { Card, Progress, Select, Tag } from "antd";

import { AppShell } from "@/components/app-shell";
import { SectionHeader } from "@/components/workflow-ui";
import { TemporalNav } from "@/components/temporal-nav";
import type {
  BacktestRecord,
  ForecastResult,
} from "@/lib/temporal";

function directionColor(d: string): string {
  if (d === "up") return "green";
  if (d === "down") return "red";
  return "blue";
}

function directionLabel(d: string): string {
  if (d === "up") return "上升";
  if (d === "down") return "下降";
  return "平稳";
}

function Sparkline({
  points,
  currentDirection,
}: {
  points: Array<{ x: number; y: number }>;
  currentDirection: string;
}) {
  if (points.length < 2) return null;
  const minX = points[0].x;
  const maxX = points[points.length - 1].x;
  const ys = points.map((p) => p.y);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const w = 480;
  const h = 80;
  const sx = (x: number) =>
    ((x - minX) / (maxX - minX || 1)) * w;
  const sy = (y: number) =>
    h - ((y - minY) / (maxY - minY || 1)) * h;
  const d = points
    .map(
      (p, i) =>
        `${i === 0 ? "M" : "L"} ${sx(p.x).toFixed(1)} ${sy(p.y).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg
      aria-label={`历史趋势：${directionLabel(currentDirection)}`}
      className={`temporal-sparkline graph-line-${currentDirection}`}
      viewBox={`0 0 ${w} ${h}`}
    >
      <path d={d} fill="none" strokeWidth="2" />
    </svg>
  );
}

export function TemporalForecastsWorkbench({
  forecasts,
  backtestRecords,
}: {
  forecasts: ForecastResult[];
  backtestRecords: BacktestRecord[];
}) {
  const [skillId, setSkillId] = useState(forecasts[0]?.skill_id ?? "");

  const skillOptions = useMemo(
    () => forecasts.map((f) => ({ label: f.skill_id, value: f.skill_id })),
    [forecasts],
  );
  const current = forecasts.find((f) => f.skill_id === skillId);

  const series = useMemo(() => {
    const filtered = backtestRecords.filter(
      (r) => r.skill_id === skillId,
    );
    const byAsOf = new Map<string, BacktestRecord[]>();
    for (const r of filtered) {
      const arr = byAsOf.get(r.as_of) ?? [];
      arr.push(r);
      byAsOf.set(r.as_of, arr);
    }
    const sorted = [...byAsOf.entries()].sort(([a], [b]) =>
      a.localeCompare(b),
    );
    return sorted.map(([asOf, recs]) => ({
      x: new Date(asOf).getTime(),
      y: recs.reduce((sum, r) => sum + r.recent, 0) / recs.length,
      label: asOf,
    }));
  }, [backtestRecords, skillId]);

  return (
    <AppShell>
      <section
        className="temporal-workbench"
        aria-labelledby="forecasts-title"
      >
        <header className="page-heading">
          <h1 id="forecasts-title">趋势回测与当前趋势</h1>
          <p>{`${forecasts.length} 条当前预测（h30 训练数据）`}</p>
        </header>
        <TemporalNav />

        <div className="temporal-filters">
          <Select
            onChange={(v) => setSkillId(String(v))}
            options={skillOptions}
            style={{ minWidth: 180 }}
            value={skillId}
          />
        </div>

        <Card
          className="temporal-forecast-card"
          title={current?.skill_id ?? "无数据"}
        >
          <div className="temporal-forecast-meta">
            <Tag color={directionColor(current?.predicted_direction ?? "flat")}>
              {directionLabel(current?.predicted_direction ?? "flat")}
            </Tag>
            <span>
              {`as_of ${current?.as_of_date ?? "–"} · 置信度 ${(
                (current?.confidence ?? 0) * 100
              ).toFixed(0)}%`}
            </span>
            <Progress
              percent={Math.round((current?.predicted_heat ?? 0) * 10)}
              showInfo={false}
              size="small"
              status={
                current?.predicted_direction === "down"
                  ? "exception"
                  : current?.predicted_direction === "up"
                    ? "success"
                    : "normal"
              }
            />
          </div>
          <Sparkline
            currentDirection={current?.predicted_direction ?? "flat"}
            points={series}
          />
        </Card>

        <section
          aria-label="当前预测列表"
          className="temporal-forecast-list"
        >
          <SectionHeader
            meta={`${forecasts.length} 条`}
            title="当前预测"
          />
          <ul>
            {forecasts.map((f) => (
              <li
                className={`temporal-forecast-list-item ${
                  f.skill_id === skillId ? "is-active" : ""
                }`}
                key={f.forecast_id}
              >
                <strong>{f.skill_id}</strong>
                <Tag color={directionColor(f.predicted_direction)}>
                  {directionLabel(f.predicted_direction)}
                </Tag>
                <span>{f.current_phase}</span>
                <small>
                  {`置信 ${(f.confidence * 100).toFixed(0)}% · ${f.as_of_date}`}
                </small>
              </li>
            ))}
          </ul>
        </section>
      </section>
    </AppShell>
  );
}