// F-T3.4 简历解析确认页：档案列表 RSC 加载（real 走 API，mock 给示例档案）。

import { ResumeParseWorkbench } from "@/components/resume-parse-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import {
  MOCK_RESUME_ARCHIVE,
  type ResumeArchiveItem,
} from "@/lib/resume-archive";

export const metadata = { title: "简历解析确认" };

export default async function ResumesPage() {
  const archive = isMockMode()
    ? MOCK_RESUME_ARCHIVE
    : await apiFetch<ResumeArchiveItem[]>("/candidates/resumes");
  return <ResumeParseWorkbench initialArchive={archive} />;
}
