import { notFound } from "next/navigation";

import { AppShell } from "@/components/app-shell";
import { DatasetDetailWorkbench } from "@/components/dataset-detail-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import type { DatasetDetail } from "@/lib/datasets";
import {
  MOCK_RESUME_ARCHIVE,
  type ResumeArchiveItem,
} from "@/lib/resume-archive";

export const metadata = { title: "数据集档案" };
export const dynamic = "force-dynamic";

export default async function DatasetDetailPage({
  params,
  searchParams,
}: Readonly<{
  params: Promise<{ datasetId: string }>;
  searchParams: Promise<{ tab?: string }>;
}>) {
  const { datasetId } = await params;
  const { tab } = await searchParams;
  const mockMode = isMockMode();

  let detail: DatasetDetail;
  if (mockMode) {
    if (datasetId !== "resumes") notFound();
    const parsed = MOCK_RESUME_ARCHIVE.filter((item) => item.stats).length;
    detail = {
      dataset: {
        id: "resumes",
        name: "简历档案",
        category: "候选人数据",
        records: MOCK_RESUME_ARCHIVE.length,
        valid_records: parsed,
        version: "resume-v2",
        status: "部分解析",
        formats: ["PDF", "DOCX"],
        source: "候选人上传与受控导入",
        updated_at: "2026-08-27T10:00:00",
        quality: 67,
        sources: [],
        count_scope: "简历档案",
        stage_counts: [
          { stage: "archive", label: "已入档", count: MOCK_RESUME_ARCHIVE.length },
          { stage: "parsed", label: "已解析", count: parsed },
        ],
      },
      versions: [
        {
          dataset_id: "resumes",
          version: "resume-v2",
          status: "部分解析",
          records: MOCK_RESUME_ARCHIVE.length,
          valid_records: parsed,
          pending_records: MOCK_RESUME_ARCHIVE.length - parsed,
          quality: 67,
          manifest_hash: "",
          manifest: {},
          run_id: "",
          imported_at: "2026-08-27T10:00:00",
        },
      ],
    };
  } else {
    try {
      detail = await apiFetch<DatasetDetail>(
        `/datasets/${encodeURIComponent(datasetId)}`,
      );
    } catch {
      notFound();
    }
  }
  const resumes: ResumeArchiveItem[] =
    datasetId === "resumes"
      ? mockMode
        ? MOCK_RESUME_ARCHIVE
        : await apiFetch<ResumeArchiveItem[]>("/candidates/resumes")
      : [];

  return (
    <AppShell>
      <DatasetDetailWorkbench
        defaultTab={tab}
        detail={detail}
        mockMode={mockMode}
        resumes={resumes}
      />
    </AppShell>
  );
}
