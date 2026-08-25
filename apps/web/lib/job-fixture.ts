import { readFile } from "node:fs/promises";
import path from "node:path";

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