import { readFile } from "node:fs/promises";
import path from "node:path";

import type { SkillGraphFixture } from "@/lib/skill";

// mock 岗位宇宙：默认岗位用三个演示态 fixture（skill.json 为手作主样本），
// 其余岗位用 skillfx.py 从真实 published 版本生成的快照（skill_<vid>.json）。
const variantFiles = {
  ready: "skill.json",
  empty: "skill_empty.json",
  error: "skill_error.json",
} as const;

export type SkillFixtureVariant = keyof typeof variantFiles;

export async function loadSkillFixture(
  variant: SkillFixtureVariant = "ready",
): Promise<SkillGraphFixture> {
  const fixturePath = path.resolve(
    process.cwd(),
    `../../data/fixtures/${variantFiles[variant]}`,
  );
  return JSON.parse(await readFile(fixturePath, "utf8")) as SkillGraphFixture;
}

export async function loadSkillFixtureForJob(
  jobVersionId: string,
): Promise<SkillGraphFixture | null> {
  const fixturePath = path.resolve(
    process.cwd(),
    `../../data/fixtures/skill_${jobVersionId}.json`,
  );
  try {
    return JSON.parse(
      await readFile(fixturePath, "utf8"),
    ) as SkillGraphFixture;
  } catch {
    return null; // 无快照的岗位回退主样本
  }
}
