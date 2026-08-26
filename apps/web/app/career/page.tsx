import { CareerHome } from "@/components/career-home";
import { AppShell } from "@/components/app-shell";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadDiagnosisFixture } from "@/lib/diagnosis-fixture";
import type { DiagnosisFixture } from "@/lib/diagnosis";

export default async function CareerPage() {
  const fixture = isMockMode() ? await loadDiagnosisFixture() : await apiFetch<DiagnosisFixture>("/diagnosis/synth_agent_senior_02");
  return <AppShell><CareerHome fixture={fixture} /></AppShell>;
}
