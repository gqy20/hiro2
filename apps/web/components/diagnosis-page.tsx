import { DiagnosisWorkbench } from "@/components/diagnosis-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { CandidateSummary } from "@/lib/api/types";
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

// ponytail: 招聘模式提供候选人切换；候选列表失败不阻断诊断页。
async function fetchCandidates(
  mode: DiagnosisMode,
): Promise<Array<{ id: string; name: string }>> {
  if (mode !== "recruiting" || isMockMode()) return [];
  try {
    const list = await apiFetch<CandidateSummary[]>("/candidates");
    return list.map((item) => ({ id: item.id, name: item.name }));
  } catch {
    return [];
  }
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
  const [fixture, candidates] = await Promise.all([
    fetchDiagnosis(variant, candidate, job),
    fetchCandidates(mode),
  ]);
  return (
    <DiagnosisWorkbench
      candidates={candidates}
      fixture={fixture}
      mode={mode}
      state={variant}
    />
  );
}
