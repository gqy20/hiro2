"use client";

const COLORS = ["var(--blue)", "var(--green)", "#a27600"];

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
  if (trends.length === 0) {
    return <div className="dashboard-trend-empty">暂无可用的趋势数据</div>;
  }
  const width = 920;
  const height = 250;
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
  return (
    <div className="dashboard-trend-chart">
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
        {trends.map((trend, index) => {
          const color = COLORS[index % COLORS.length];
          const last = trend.values.length - 1;
          const x = xAt(last, trend.values.length);
          const y = yAt(trend.values[last]);
          return (
            <g key={trend.skill_id}>
              <path d={path(trend.values)} style={{ stroke: color }} />
              <circle cx={x} cy={y} r="3.5" style={{ fill: color }} />
            </g>
          );
        })}
        {trends[0]?.months.map((month, index) =>
          index % 2 === 0 ? (
            <text
              key={month}
              x={xAt(index, trends[0].months.length)}
              y={height - 2}
              textAnchor="middle"
              className="dashboard-chart-label"
            >
              {month.slice(2)}
            </text>
          ) : null,
        )}
      </svg>
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
