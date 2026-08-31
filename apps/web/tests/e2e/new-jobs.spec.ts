import { expect, test } from "@playwright/test";

test("accepts candidate and edits five definition fields", async ({ page }) => {
  await page.goto("/new-jobs");

  const acceptButton = page.getByRole("button", { name: "接受候选" });
  await acceptButton.click();
  await expect(page.locator(".status-mark").first()).toContainText(/已确认/);

  // 决定后审核栏切换为承接状态，可本地恢复待审
  await expect(page.locator(".candidate-review-bar")).toContainText(
    "已接受为岗位定义草稿",
  );
  await page.getByRole("button", { name: "恢复待审" }).click();
  await expect(page.getByRole("button", { name: "接受候选" })).toBeVisible();

  await page.getByRole("button", { name: "编辑定义" }).click();
  await expect(page.locator(".definition-editor")).toBeVisible();

  await page.getByLabel("岗位名称").fill("e2e 测试岗位");
  await page.getByLabel("摘要").fill("e2e 测试摘要");
  await page.getByLabel("核心职责").fill("职责 1\n职责 2");
  await page.getByLabel("必备技能").fill("技能 A");
  await page.getByRole("button", { name: "保存定义" }).click();

  await expect(
    page.getByRole("heading", { name: "e2e 测试岗位", level: 2 }),
  ).toBeVisible();
  await expect(page.locator(".definition-editor")).toHaveCount(0);
});

test("renders empty and error variants", async ({ page }) => {
  await page.goto("/new-jobs?state=empty");
  await expect(page.getByText("当前时间窗没有新的岗位候选。")).toBeVisible();

  await page.goto("/new-jobs?state=error");
  await expect(page.getByText("候选岗位来源暂时不可用。")).toBeVisible();
});
