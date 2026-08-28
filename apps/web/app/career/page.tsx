import { AppShell } from "@/components/app-shell";
import { CareerHome, CareerHomeEmpty } from "@/components/career-home";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadDiagnosisFixture } from "@/lib/diagnosis-fixture";
import type { DiagnosisFixture } from "@/lib/diagnosis";

export const dynamic = "force-dynamic";

type CareerHomeState =
  | { status: "ready"; candidateId: string; jobVersionId: string }
  | { status: "empty" };

export default async function CareerPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  if (isMockMode()) {
    if (state === "empty") {
      return (
        <AppShell>
          <CareerHomeEmpty />
        </AppShell>
      );
    }
    return (
      <AppShell>
        <CareerHome fixture={await loadDiagnosisFixture()} />
      </AppShell>
    );
  }
  const home = await apiFetch<CareerHomeState>("/career/home");
  if (home?.status !== "ready") {
    return (
      <AppShell>
        <CareerHomeEmpty />
      </AppShell>
    );
  }
  const fixture = await apiFetch<DiagnosisFixture>(
    `/diagnosis/${home.candidateId}?job=${encodeURIComponent(home.jobVersionId)}`,
  );
  return (
    <AppShell>
      <CareerHome fixture={fixture} />
    </AppShell>
  );
}
