import { AppShell } from "@/components/app-shell";

export default function EvaluationPage() {
  return (
    <AppShell>
      <section className="pending-page" aria-labelledby="evaluation-title">
        <div>
          <p className="route-label">模块建设中</p>
          <h1 id="evaluation-title">评测中心</h1>
        </div>
        <p>
          评测中心将在 F-T4.1 接入 `Evaluation API`；当前页面占位以便一级导航可达。
        </p>
      </section>
    </AppShell>
  );
}