import { AppShell } from "@/components/app-shell";

type LoadVariant =
  | "career"
  | "dashboard"
  | "data"
  | "diagnosis"
  | "evaluation"
  | "jobs"
  | "new-jobs"
  | "quality"
  | "skills"
  | "tasks"
  | "temporal";

function LoadPanel({
  className = "",
  rows = 4,
}: {
  className?: string;
  rows?: number;
}) {
  return (
    <div className={`load-panel ${className}`}>
      <i className="load-title" />
      {Array.from({ length: rows }, (_, index) => (
        <i className="load-line" key={index} />
      ))}
    </div>
  );
}

export function LoadView({ variant }: { variant: LoadVariant }) {
  const isThreeColumn = ["diagnosis", "evaluation", "jobs", "skills"].includes(
    variant,
  );
  return (
    <AppShell>
      <section
        className={`route-loading route-loading-${variant}`}
        aria-busy="true"
        aria-label="正在加载页面"
        aria-live="polite"
      >
        <div className="load-context">
          <i />
          <i />
          <i />
        </div>
        <header className="load-heading">
          <i />
          <i />
        </header>
        {variant === "dashboard" ? (
          <div className="load-dashboard">
            <LoadPanel className="load-focus" rows={3} />
            <LoadPanel rows={3} />
            <LoadPanel className="load-chart" rows={5} />
            <LoadPanel rows={3} />
          </div>
        ) : variant === "data" ? (
          <div className="load-data">
            <LoadPanel className="load-data-kpis" rows={2} />
            <LoadPanel className="load-primary" rows={5} />
            <LoadPanel rows={1} />
          </div>
        ) : isThreeColumn ? (
          <div className="load-three-column">
            <LoadPanel
              className="load-side"
              rows={variant === "skills" ? 5 : 7}
            />
            <LoadPanel
              className="load-primary"
              rows={variant === "jobs" ? 10 : 7}
            />
            <LoadPanel className="load-side" rows={6} />
          </div>
        ) : variant === "new-jobs" || variant === "tasks" ? (
          <div className="load-two-column">
            <LoadPanel rows={8} />
            <LoadPanel className="load-primary" rows={9} />
          </div>
        ) : (
          <div className="load-grid">
            <LoadPanel rows={3} />
            <LoadPanel rows={4} />
            <LoadPanel rows={5} />
            <LoadPanel rows={3} />
          </div>
        )}
      </section>
    </AppShell>
  );
}
