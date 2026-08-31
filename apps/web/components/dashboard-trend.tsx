"use client";

import { useRef, useState } from "react";

const COLORS = ["var(--blue)", "var(--green)", "#a27600"];

const CHART_WIDTH = 920;
const CHART_HEIGHT = 250;

export function DashboardTrend({
  trends,
}: {
  trends: Array<{
    skill_id: string;
    label: string;
    months: string[];
    values: number[];
    sample_counts: number[];
  }>;
}) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);

  if (trends.length === 0) {
    return <div className="dashboard-trend-empty">暂无可用的趋势数据</div>;
  }
  const width = CHART_WIDTH;
  const height = CHART_HEIGHT;
  const months = trends[0]?.months ?? [];
  const all = trends.flatMap((trend) => trend.values);
  const min = Math.min(...all, 0);
  const max = Math.max(...all, 1);
  const xAt = (index: number, count: number) =>
    (index / Math.max(count - 1, 1)) * (width - 28) + 14;
  const yAt = (value: number) =>
    height - ((value - min) / Math.max(max - min, 1)) * (height - 40) - 20;
  const path = (values: number[]) =>
    values
      .map((value, index) => {
        const x = xAt(index, values.length);
        const y = yAt(value);
        if (index === 0) return `M${x.toFixed(1)},${y.toFixed(1)}`;
        const previousX = xAt(index - 1, values.length);
        const previousY = yAt(values[index - 1]);
        const mid = (previousX + x) / 2;
        return `C${mid.toFixed(1)},${previousY.toFixed(1)} ${mid.toFixed(1)},${y.toFixed(1)} ${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  const gridValues = [0, 25, 50, 75, 100];

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    const stage = stageRef.current;
    if (!stage || months.length === 0) return;
    const rect = stage.getBoundingClientRect();
    const viewX = ((event.clientX - rect.left) / rect.width) * width;
    const ratio = (viewX - 14) / (width - 28);
    const index = Math.round(ratio * (months.length - 1));
    setHoverIndex(Math.max(0, Math.min(months.length - 1, index)));
  }

  const hovered = hoverIndex !== null ? months[hoverIndex] : null;
  // 靠右时把提示框翻到竖线左侧，避免溢出
  const flipTooltip =
    hoverIndex !== null && hoverIndex > (months.length - 1) * 0.6;

  return (
    <div className="dashboard-trend-chart">
      <div
        className="dashboard-trend-stage"
        onPointerLeave={() => setHoverIndex(null)}
        onPointerMove={handlePointerMove}
        ref={stageRef}
      >
        <svg
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label="近期开启岗位能力需求趋势"
        >
          {gridValues.map((value) => {
            const y = yAt(value);
            return (
              <g key={value}>
                <line
                  x1="14"
                  y1={y}
                  x2={width - 14}
                  y2={y}
                  className="dashboard-chart-grid"
                />
                <text x="0" y={y + 4} className="dashboard-chart-label">
                  {value}
                </text>
              </g>
            );
          })}
          <text x="0" y="13" className="dashboard-chart-label">
            提及率 %
          </text>
          {hoverIndex !== null ? (
            <line
              className="dashboard-chart-hoverline"
              x1={xAt(hoverIndex, months.length)}
              x2={xAt(hoverIndex, months.length)}
              y1={16}
              y2={height - 24}
            />
          ) : null}
          {trends.map((trend, index) => {
            const color = COLORS[index % COLORS.length];
            const last = trend.values.length - 1;
            const x = xAt(last, trend.values.length);
            const y = yAt(trend.values[last]);
            return (
              <g key={trend.skill_id}>
                <path d={path(trend.values)} style={{ stroke: color }} />
                <circle cx={x} cy={y} r="3.5" style={{ fill: color }} />
                {hoverIndex !== null && trend.values[hoverIndex] != null ? (
                  <circle
                    cx={xAt(hoverIndex, trend.values.length)}
                    cy={yAt(trend.values[hoverIndex])}
                    r="4"
                    style={{ fill: color }}
                  />
                ) : null}
              </g>
            );
          })}
          {months.map((month, index) =>
            index % 2 === 0 ? (
              <text
                key={month}
                x={xAt(index, months.length)}
                y={height - 2}
                textAnchor="middle"
                className="dashboard-chart-label"
              >
                {month.slice(2)}
              </text>
            ) : null,
          )}
        </svg>
        {hoverIndex !== null && hovered ? (
          <div
            className="dashboard-trend-tooltip"
            style={{
              left: `${(xAt(hoverIndex, months.length) / width) * 100}%`,
              transform: flipTooltip
                ? "translateX(calc(-100% - 10px))"
                : "translateX(10px)",
            }}
          >
            <strong>{hovered}</strong>
            {trends.map((trend, index) => (
              <span key={trend.skill_id}>
                <i style={{ background: COLORS[index % COLORS.length] }} />
                {trend.label}
                <b>{`${(trend.values[hoverIndex] ?? 0).toFixed(1)}%`}</b>
                <small>{`样本 ${trend.sample_counts[hoverIndex] ?? 0}`}</small>
              </span>
            ))}
          </div>
        ) : null}
      </div>
      <div className="dashboard-trend-legend">
        {trends.map((trend, index) => (
          <span key={trend.skill_id}>
            <i style={{ background: COLORS[index % COLORS.length] }} />
            {trend.label}
          </span>
        ))}
      </div>
    </div>
  );
}
