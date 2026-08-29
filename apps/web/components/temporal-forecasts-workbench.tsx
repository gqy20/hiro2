"use client";

import { useMemo, useState } from "react";
import { Select, Tag } from "antd";

import type { BacktestRecord, ForecastResult } from "@/lib/temporal";
import { skillDisplay } from "@/lib/skill-labels";

function directionColor(direction: string): string {
  if (direction === "up") return "green";
  if (direction === "down") return "red";
  return "blue";
}

function directionLabel(direction: string): string {
  if (direction === "up") return "上升";
  if (direction === "down") return "下降";
  return "平稳";
}

function phaseLabel(phase: string): string {
  if (phase === "rising" || phase === "up") return "上升期";
  if (phase === "falling" || phase === "down") return "下降期";
  if (phase === "stable" || phase === "flat") return "平稳期";
  return phase || "未判定";
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
  const ys = points.map((point) => point.y);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const width = 480;
  const height = 80;
  const scaleX = (x: number) => ((x - minX) / (maxX - minX || 1)) * width;
  const scaleY = (y: number) =>
    height - ((y - minY) / (maxY - minY || 1)) * height;
  const path = points
    .map(
      (point, index) =>
        `${index === 0 ? "M" : "L"} ${scaleX(point.x).toFixed(1)} ${scaleY(point.y).toFixed(1)}`,
    )
    .join(" ");
  return (
    <svg
      aria-label={`历史趋势：${directionLabel(currentDirection)}`}
      className={`temporal-sparkline graph-line-${currentDirection}`}
      viewBox={`0 0 ${width} ${height}`}
    >
      <path d={path} fill="none" strokeWidth="2" />
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
  const current = forecasts.find((forecast) => forecast.skill_id === skillId);
  const currentRecord = useMemo(
    () =>
      backtestRecords
        .filter((record) => record.skill_id === skillId)
        .sort((a, b) => b.rule_version - a.rule_version)[0],
    [backtestRecords, skillId],
  );
  const changeRate =
    currentRecord && currentRecord.prior !== 0
      ? (currentRecord.recent - currentRecord.prior) / currentRecord.prior
      : null;

  const series = useMemo(() => {
    const filtered = backtestRecords.filter(
      (record) => record.skill_id === skillId,
    );
    const byAsOf = new Map<string, BacktestRecord[]>();
    for (const record of filtered) {
      const values = byAsOf.get(record.as_of) ?? [];
      values.push(record);
      byAsOf.set(record.as_of, values);
    }
    return [...byAsOf.entries()]
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([asOf, records]) => ({
        x: new Date(asOf).getTime(),
        y:
          records.reduce((sum, record) => sum + record.recent, 0) /
          records.length,
      }));
  }, [backtestRecords, skillId]);

  return (
    <section className="temporal-workbench" aria-label="趋势预测">
      <div className="temporal-forecast-toolbar">
        <div>
          <strong>{`${forecasts.length} 个能力域`}</strong>
          <span>预测未来 30 天</span>
        </div>
        <Select
          aria-label="选择能力域"
          onChange={(value) => setSkillId(String(value))}
          options={forecasts.map((forecast) => ({
            label: skillDisplay(forecast.skill_id),
            value: forecast.skill_id,
          }))}
          value={skillId}
        />
      </div>

      <section
        className="temporal-forecast-summary"
        aria-label="当前能力域预测"
      >
        <header>
          <div>
            <strong>
              {current ? skillDisplay(current.skill_id) : "无数据"}
            </strong>
            <Tag color={directionColor(current?.predicted_direction ?? "flat")}>
              {directionLabel(current?.predicted_direction ?? "flat")}
            </Tag>
          </div>
          <span>{`截至 ${current?.as_of_date ?? "未记录"}`}</span>
        </header>
        <dl>
          <div>
            <dt>当前热度</dt>
            <dd>{current?.predicted_heat?.toFixed(1) ?? "-"}</dd>
          </div>
          <div>
            <dt>较前期</dt>
            <dd
              className={
                changeRate !== null && changeRate < 0 ? "is-down" : "is-up"
              }
            >
              {changeRate === null
                ? "暂无"
                : `${changeRate > 0 ? "+" : ""}${(changeRate * 100).toFixed(1)}%`}
            </dd>
          </div>
          <div>
            <dt>置信度</dt>
            <dd>{`${((current?.confidence ?? 0) * 100).toFixed(0)}%`}</dd>
          </div>
          <div>
            <dt>阶段</dt>
            <dd>{phaseLabel(current?.current_phase ?? "")}</dd>
          </div>
        </dl>
        <Sparkline
          currentDirection={current?.predicted_direction ?? "flat"}
          points={series}
        />
      </section>

      <section
        className="temporal-forecast-table"
        aria-labelledby="forecast-table-title"
      >
        <div className="temporal-forecast-table-title">
          <h2 id="forecast-table-title">能力域预测</h2>
          <span>{`${forecasts.length} 条`}</span>
        </div>
        <div className="temporal-forecast-table-wrap">
          <table className="t-table">
            <colgroup>
              <col className="col-skill" />
              <col className="col-direction" />
              <col className="col-phase" />
              <col className="col-confidence" />
              <col className="col-date" />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">能力域</th>
                <th scope="col">方向</th>
                <th scope="col">阶段</th>
                <th className="num" scope="col">
                  置信度
                </th>
                <th className="num" scope="col">
                  截止日期
                </th>
              </tr>
            </thead>
            <tbody>
              {forecasts.map((forecast) => (
                <tr
                  aria-selected={forecast.skill_id === skillId}
                  className={
                    forecast.skill_id === skillId ? "is-active" : undefined
                  }
                  key={forecast.forecast_id}
                  onClick={() => setSkillId(forecast.skill_id)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      setSkillId(forecast.skill_id);
                    }
                  }}
                  tabIndex={0}
                >
                  <th scope="row">{skillDisplay(forecast.skill_id)}</th>
                  <td>
                    <Tag color={directionColor(forecast.predicted_direction)}>
                      {directionLabel(forecast.predicted_direction)}
                    </Tag>
                  </td>
                  <td className="forecast-phase">
                    {phaseLabel(forecast.current_phase)}
                  </td>
                  <td className="num forecast-confidence">
                    {`${(forecast.confidence * 100).toFixed(0)}%`}
                  </td>
                  <td className="num">
                    <time dateTime={forecast.as_of_date}>
                      {forecast.as_of_date}
                    </time>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </section>
  );
}
