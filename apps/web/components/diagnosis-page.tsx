import { DiagnosisWorkbench } from "@/components/diagnosis-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadDiagnosisFixture } from "@/lib/diagnosis-fixture";
import type { DiagnosisView } from "@/lib/api/types";

type DiagnosisVariant = "ready" | "empty" | "error";
type DiagnosisMode = "recruiting" | "career";
type DiagnosisSearchParams = {
  state?: string;
  candidate?: string;
  job?: string;
};

const DEFAULT_CANDIDATE = "synth_agent_senior_02";

async function fetchDiagnosis(
  variant: DiagnosisVariant,
  candidate?: string,
  job?: string,
): Promise<DiagnosisView> {
  if (isMockMode() || variant !== "ready") {
    return loadDiagnosisFixture(variant);
  }
  return apiFetch<DiagnosisView>(
    `/diagnosis/${encodeURIComponent(candidate || DEFAULT_CANDIDATE)}${job ? `?job=${encodeURIComponent(job)}` : ""}`,
  );
}

export async function DiagnosisPageView({
  mode,
  searchParams,
}: {
  mode: DiagnosisMode;
  searchParams: Promise<DiagnosisSearchParams>;
}) {
  const { state, candidate, job } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  return (
    <DiagnosisWorkbench
      fixture={await fetchDiagnosis(variant, candidate, job)}
      mode={mode}
      state={variant}
    />
  );
}
