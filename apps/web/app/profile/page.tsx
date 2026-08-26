import { AppShell } from "@/components/app-shell";
import { ProfileWorkbench } from "@/components/profile-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadDiagnosisFixture } from "@/lib/diagnosis-fixture";
import type { DiagnosisFixture } from "@/lib/diagnosis";

export default async function ProfilePage() {
  const fixture = isMockMode() ? await loadDiagnosisFixture() : await apiFetch<DiagnosisFixture>("/diagnosis/synth_agent_senior_02");
  return <AppShell><ProfileWorkbench fixture={fixture} /></AppShell>;
}
