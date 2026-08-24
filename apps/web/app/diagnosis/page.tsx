import { DiagnosisWorkbench } from "@/components/diagnosis-workbench";
import { loadDiagnosisFixture } from "@/lib/diagnosis-fixture";

export default async function DiagnosisPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  return (
    <DiagnosisWorkbench
      fixture={await loadDiagnosisFixture(variant)}
      state={variant}
    />
  );
}
