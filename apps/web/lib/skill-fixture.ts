import { readFile } from "node:fs/promises";
import path from "node:path";

import type { SkillGraphFixture } from "@/lib/skill";

const files = {
  empty: "skill_empty.json",
  error: "skill_error.json",
  ready: "skill.json",
} as const;

export type SkillFixtureVariant = keyof typeof files;

export async function loadSkillFixture(
  variant: SkillFixtureVariant = "ready",
): Promise<SkillGraphFixture> {
  const fixturePath = path.resolve(
    process.cwd(),
    `../../data/fixtures/${files[variant]}`,
  );
  return JSON.parse(await readFile(fixturePath, "utf8")) as SkillGraphFixture;
}
