"use client";

type Tone = "default" | "accent";

type Props = Readonly<{
  label: string;
  value: string;
  meta?: string;
  variant?: "primary" | "secondary";
  sparkline?: number[];
  tone?: Tone;
}>;

function Sparkline({ values }: { values: number[] }) {
  if (values.length < 2) {
    return (
      <svg
        aria-hidden
        className="data-kpi-sparkline is-empty"
        height={28}
        viewBox="0 0 120 28"
        width={120}
      >
        <line
          stroke="currentColor"
          strokeDasharray="3 3"
          x1="0"
          x2="120"
          y1="14"
          y2="14"
        />
      </svg>
    );
  }
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = 120 / (values.length - 1);
  const points = values
    .map((v, i) => `${(i * step).toFixed(1)},${(24 - ((v - min) / range) * 22).toFixed(1)}`)
    .join(" ");
  return (
    <svg
      aria-hidden
      className="data-kpi-sparkline"
      height={28}
      viewBox="0 0 120 28"
      width={120}
    >
      <polyline fill="none" points={points} stroke="currentColor" />
    </svg>
  );
}

function formatNumber(n: number): string {
  return n.toLocaleString("zh-CN");
}

export function DataKpiCard({
  label,
  value,
  meta,
  variant = "secondary",
  sparkline,
  tone = "default",
}: Props) {
  const isPrimary = variant === "primary";
  return (
    <div
      className={`data-kpi data-kpi-${variant} data-kpi-tone-${tone}`}
      role="group"
    >
      <span className="data-kpi-label">{label}</span>
      <strong className="data-kpi-value">{value}</strong>
      {meta ? <span className="data-kpi-meta">{meta}</span> : null}
      {isPrimary && sparkline !== undefined ? (
        <Sparkline values={sparkline} />
      ) : null}
    </div>
  );
}

export { formatNumber };