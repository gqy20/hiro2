import { readFile } from "node:fs/promises";
import path from "node:path";

import type { NewJobsFixture } from "@/lib/new-jobs";

const fixtureFiles = {
  empty: "new_jobs_empty.json",
  error: "new_jobs_error.json",
  ready: "new_jobs.json",
} as const;

export async function loadNewJobsFixture(
  variant: keyof typeof fixtureFiles = "ready",
): Promise<NewJobsFixture> {
  const fixturePath = path.resolve(
    process.cwd(),
    `../../data/fixtures/${fixtureFiles[variant]}`,
  );
  return JSON.parse(await readFile(fixturePath, "utf8")) as NewJobsFixture;
}
