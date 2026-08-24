import { readFile } from "node:fs/promises";
import path from "node:path";

import type { DiagnosisFixture } from "@/lib/diagnosis";

const files = {
  empty: "diagnosis_empty.json",
  error: "diagnosis_error.json",
  ready: "diagnosis.json",
} as const;

export async function loadDiagnosisFixture(
  variant: keyof typeof files = "ready",
): Promise<DiagnosisFixture> {
  const file = path.resolve(
    process.cwd(),
    `../../data/fixtures/${files[variant]}`,
  );
  return JSON.parse(await readFile(file, "utf8")) as DiagnosisFixture;
}
