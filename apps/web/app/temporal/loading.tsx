export default function Loading() {
  return (
    <section
      aria-busy="true"
      aria-label="正在加载趋势洞察"
      aria-live="polite"
      className="trend-loading"
    >
      <div className="trend-loading-toolbar" />
      <div className="trend-loading-grid">
        <div />
        <div />
        <div />
      </div>
    </section>
  );
}
