// F-T3.4 简历解析确认页：档案列表 RSC 加载（real 走 API，mock 给示例档案）。

import { ResumeParseWorkbench } from "@/components/resume-parse-workbench";
import type { ResumeArchiveItem } from "@/components/resume-parse-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";

export const metadata = { title: "简历解析确认" };

const MOCK_ARCHIVE: ResumeArchiveItem[] = [
  {
    resume_id: "res-mock-01",
    filename: "div_variant_agent_00.pdf",
    size: 184_320,
    suffix: ".pdf",
    uploaded_at: "2026-08-27T10:00:00",
    source: "upload",
    stats: {
      totalSkills: 12,
      resolved: 11,
      byDict: 9,
      byLlm: 2,
      unresolved: 1,
    },
  },
  {
    resume_id: "res-mock-02",
    filename: "div_buried_career_change_11.pdf",
    size: 165_100,
    suffix: ".pdf",
    uploaded_at: "2026-08-26T18:30:00",
    source: "imported",
    stats: null,
  },
  {
    resume_id: "res-mock-03",
    filename: "div_noisy_llm_12.docx",
    size: 98_304,
    suffix: ".docx",
    uploaded_at: "2026-08-26T18:30:00",
    source: "imported",
    stats: null,
  },
];

export default async function ResumesPage() {
  const archive = isMockMode()
    ? MOCK_ARCHIVE
    : await apiFetch<ResumeArchiveItem[]>("/candidates/resumes");
  return <ResumeParseWorkbench initialArchive={archive} />;
}
