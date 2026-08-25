import { expect, test } from "@playwright/test";

test("accepts all changes and publishes target version", async ({ page }) => {
  await page.goto("/jobs");

  // 收集所有「接受 X」按钮的 accessible name，一次性点完
  // （点过的按钮会从 DOM 消失，所以必须先收集）
  const names = await page
    .getByRole("button", { name: /^接受 / })
    .evaluateAll((els) => els.map((el) => el.getAttribute("aria-label") ?? ""));
  for (const name of names) {
    await page.getByRole("button", { name }).first().click();
  }

  await expect(page.getByText("审核完成，可发布新版本")).toBeVisible();

  await page.getByRole("button", { name: "发布版本" }).click();
  await expect(page.getByText("发布岗位版本")).toBeVisible();

  await page.getByRole("button", { name: /^发布 v/ }).click();

  await expect(
    page.getByRole("heading", { name: "岗位版本已发布" }),
  ).toBeVisible({ timeout: 5000 });
  await expect(page.getByText(/^已接受/)).toBeVisible();
  await expect(page.getByText(/^已拒绝/)).toBeVisible();

  await page.getByRole("button", { name: "返回岗位更新" }).click();
  await expect(
    page.getByRole("heading", { name: "岗位更新", level: 1 }),
  ).toBeVisible();
});

test("renders empty and error variants", async ({ page }) => {
  await page.goto("/jobs?state=empty");
  await expect(page.getByText("当前版本暂未检测到能力变化。")).toBeVisible();

  await page.goto("/jobs?state=error");
  await expect(page.getByText("岗位版本数据暂时不可用")).toBeVisible();
});