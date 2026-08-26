import { DiagnosisWorkbench } from "@/components/diagnosis-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadDiagnosisFixture } from "@/lib/diagnosis-fixture";
import type { DiagnosisView } from "@/lib/api/types";

type DiagnosisVariant = "ready" | "empty" | "error";
const DEFAULT_CANDIDATE = "synth_agent_senior_02";

// ponytail: RSC 页面直接处理 mock/real 切换（与 jobs/new-jobs 页同一模式）。
async function fetchDiagnosisServer(
  variant: DiagnosisVariant,
  candidate?: string,
  job?: string,
): Promise<DiagnosisView> {
  if (isMockMode()) return loadDiagnosisFixture(variant);
  if (variant !== "ready") return loadDiagnosisFixture(variant); // 边界态保留 fixture 联调
  return apiFetch<DiagnosisView>(
    `/diagnosis/${encodeURIComponent(candidate || DEFAULT_CANDIDATE)}${job ? `?job=${encodeURIComponent(job)}` : ""}`,
  );
}

export default async function DiagnosisPage({
  searchParams,
}: Readonly<{
  searchParams: Promise<{ state?: string; candidate?: string; job?: string }>;
}>) {
  const { state, candidate, job } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  return (
    <DiagnosisWorkbench
      fixture={await fetchDiagnosisServer(variant, candidate, job)}
      state={variant}
    />
  );
}
