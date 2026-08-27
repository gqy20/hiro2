import { SkillsWorkbench } from "@/components/skills-workbench";
import { apiFetch, isMockMode } from "@/lib/api/client";
import { loadSkillFixture } from "@/lib/skill-fixture";
import type { SkillGraphView } from "@/lib/api/types";

type SkillGraphVariant = "ready" | "empty" | "error";

// ponytail: RSC 页面直接处理 mock/real 切换，不通过 lib/api/queries.ts，
// 避免 node:fs/promises 被拉进客户端 bundle。
async function fetchSkillServer(
  variant: SkillGraphVariant,
): Promise<SkillGraphView> {
  if (isMockMode()) return loadSkillFixture(variant);
  return apiFetch<SkillGraphView>(`/skills/graph?state=${variant}`);
}

export default async function SkillsPage({
  searchParams,
}: Readonly<{ searchParams: Promise<{ state?: string }> }>) {
  const { state } = await searchParams;
  const variant = state === "empty" || state === "error" ? state : "ready";
  return (
    <SkillsWorkbench
      fixture={await fetchSkillServer(variant)}
      state={variant}
    />
  );
}
