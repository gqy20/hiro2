import { AppShell } from "@/components/app-shell";
import { CareerPath } from "@/components/career-path";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadDiagnosisFixture } from "@/lib/diagnosis-fixture";
import type { DiagnosisFixture } from "@/lib/diagnosis";

export const dynamic = "force-dynamic";

export default async function CareerPathPage() {
  const fixture: DiagnosisFixture = isMockMode()
    ? await loadDiagnosisFixture()
    : await apiFetch<DiagnosisFixture>("/diagnosis/synth_agent_senior_02");
  return (
    <AppShell>
      <CareerPath fixture={fixture} />
    </AppShell>
  );
}
