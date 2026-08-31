"use client";

import { useMemo } from "react";

/**
 * 涌现候选的月度 JD 量迷你柱状图（纯 SVG，无图表库依赖）。
 * 数据来自 emergscan 的 monthly（{"2026-05": 6, ...}）。
 * 月份不全时补零，保证时间轴连续。
 */
export function TrendSparkline({
  monthly,
  summary,
}: {
  monthly?: Record<string, number>;
  summary?: string;
}) {
  const { bars, peak } = useMemo(() => {
    if (!monthly || Object.keys(monthly).length === 0) return { bars: [], peak: 0 };
    const keys = Object.keys(monthly).sort();
    const start = new Date(`${keys[0]}-01`);
    const end = new Date(`${keys[keys.length - 1]}-01`);
    const out: { label: string; count: number }[] = [];
    const cursor = new Date(start);
    while (cursor <= end) {
      const key = cursor.toISOString().slice(0, 7);
      out.push({ label: key, count: monthly[key] ?? 0 });
      cursor.setUTCMonth(cursor.getUTCMonth() + 1);
    }
    return { bars: out, peak: Math.max(...out.map((b) => b.count), 1) };
  }, [monthly]);

  if (bars.length === 0) return null;

  return (
    <figure className="trend-sparkline" aria-label="月度 JD 数量趋势">
      <div className="trend-bars">
        {bars.map((b) => (
          <div className="trend-bar-col" key={b.label} title={`${b.label}：${b.count} 条`}>
            <div
              className="trend-bar"
              style={{ height: `${Math.max((b.count / peak) * 100, b.count > 0 ? 4 : 1)}%` }}
            />
            <span className="trend-bar-value">{b.count > 0 ? b.count : ""}</span>
          </div>
        ))}
      </div>
      <figcaption>
        <span>{bars[0].label.slice(2)}</span>
        <span>{summary}</span>
        <span>{bars[bars.length - 1].label.slice(2)}</span>
      </figcaption>
    </figure>
  );
}
