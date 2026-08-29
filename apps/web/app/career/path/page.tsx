import { AppShell } from "@/components/app-shell";
import { CareerPath } from "@/components/career-path";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadDiagnosisFixture } from "@/lib/diagnosis-fixture";
import type { DiagnosisFixture } from "@/lib/diagnosis";

export const dynamic = "force-dynamic";

export default async function CareerPathPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  if (state === "error") {
    return (
      <AppShell>
        <FixtureState
          errorText="学习路径数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  }
  if (state === "empty") {
    return (
      <AppShell>
        <FixtureState
          emptyText="选择目标岗位并完成诊断后生成学习路径。"
          state="empty"
        />
      </AppShell>
    );
  }
  const fixture: DiagnosisFixture = isMockMode()
    ? await loadDiagnosisFixture()
    : await apiFetch<DiagnosisFixture>("/diagnosis/synth_agent_senior_02");
  return (
    <AppShell>
      <CareerPath fixture={fixture} />
    </AppShell>
  );
}
