import { readFile } from "node:fs/promises";
import path from "node:path";

import type { DetectedChangesView } from "@/lib/api/types";
import type { JobUpdateFixture } from "@/lib/job-update";

const files = {
  empty: "job_update_empty.json",
  error: "job_update_error.json",
  ready: "job_update.json",
} as const;

export type JobUpdateFixtureVariant = keyof typeof files;

export async function loadJobUpdateFixture(
  variant: JobUpdateFixtureVariant = "ready",
): Promise<JobUpdateFixture> {
  const fixturePath = path.resolve(
    process.cwd(),
    `../../data/fixtures/${files[variant]}`,
  );
  return JSON.parse(await readFile(fixturePath, "utf8")) as JobUpdateFixture;
}

// ponytail: 快照差异检测草稿的 mock 样本，字段与后端 DetectedChangesVM 一致。
export async function loadDetectedChangesFixture(): Promise<DetectedChangesView> {
  const fixturePath = path.resolve(
    process.cwd(),
    "../../data/fixtures/detected_changes.json",
  );
  return JSON.parse(await readFile(fixturePath, "utf8")) as DetectedChangesView;
}
