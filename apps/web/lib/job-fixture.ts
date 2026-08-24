import { readFile } from "node:fs/promises";
import path from "node:path";

import type { JobUpdateFixture } from "@/lib/job-update";

const fixturePath = path.resolve(
  process.cwd(),
  "../../data/fixtures/job_update.json",
);

export async function loadJobUpdateFixture(): Promise<JobUpdateFixture> {
  const fixture = await readFile(fixturePath, "utf8");
  return JSON.parse(fixture) as JobUpdateFixture;
}
