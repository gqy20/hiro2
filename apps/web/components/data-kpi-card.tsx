type Props = Readonly<{
  label: string;
  value: string;
  suffix?: string;
}>;

export function DataKpiCard({ label, value, suffix }: Props) {
  return (
    <div className="data-kpi" role="group">
      <span className="data-kpi-label">{label}</span>
      <span className="data-kpi-value-row">
        <strong className="data-kpi-value">{value}</strong>
        {suffix ? <span className="data-kpi-suffix">{suffix}</span> : null}
      </span>
    </div>
  );
}
