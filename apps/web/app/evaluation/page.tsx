import { AppShell } from "@/components/app-shell";
import { DataQualityWorkbench } from "@/components/data-quality-workbench";
import { EvaluationWorkbench } from "@/components/evaluation-workbench";
import { QualityWorkbench } from "@/components/quality-workbench";
import { FixtureState } from "@/components/workflow-ui";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadEvaluationFixture } from "@/lib/evaluation-fixture";
import { loadQualityFixture, type QualityOverview } from "@/lib/quality";
import { loadTemporalFixture } from "@/lib/temporal-fixture";
import type { EvaluationOverview } from "@/lib/evaluation";
import type { TemporalDataset } from "@/lib/temporal";

export const metadata = { title: "评测与质量" };

export const dynamic = "force-dynamic";

const EMPTY_QUALITY: QualityOverview = {
  source: "file",
  dataset_version: "",
  task_total: 0,
  task_resolved: 0,
  completion_rate: 0,
  dual_review_rate: null,
  avg_response_days: null,
  error_distribution: {},
  data_quality: {},
};

export default async function EvaluationPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  if (variant === "error") {
    return (
      <AppShell>
        <FixtureState
          errorText="评测数据暂时不可用，请稍后重试。"
          state="error"
        />
      </AppShell>
    );
  }
  if (variant === "empty") {
    return (
      <AppShell>
        <FixtureState emptyText="暂无回测运行记录。" state="empty" />
      </AppShell>
    );
  }

  const [overview, quality, temporal]: [
    EvaluationOverview,
    QualityOverview,
    TemporalDataset,
  ] = isMockMode()
    ? [
        await loadEvaluationFixture(),
        await loadQualityFixture(),
        await loadTemporalFixture(),
      ]
    : [
        await apiFetch<EvaluationOverview>("/evaluation/overview"),
        (await apiFetch<QualityOverview>("/quality/overview")) ?? EMPTY_QUALITY,
        await apiFetch<TemporalDataset>("/temporal/dataset"),
      ];

  return (
    <EvaluationWorkbench
      extra={
        <>
          <DataQualityWorkbench embedded quality={quality} />
          <QualityWorkbench embedded quality={quality} temporal={temporal} />
        </>
      }
      overview={overview}
    />
  );
}
