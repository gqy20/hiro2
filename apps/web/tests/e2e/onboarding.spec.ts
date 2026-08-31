import { expect, test } from "@playwright/test";

test("first visit opens onboarding tour, closes and reopens via help button", async ({
  page,
}) => {
  await page.goto("/");

  // 首访自动弹出引导（招聘区欢迎语）
  await expect(page.locator(".ant-tour")).toBeVisible();
  await expect(page.getByText("欢迎来到招聘工作区")).toBeVisible();

  // 步骤推进（锚定 Tour 内按钮，避开 Next.js Dev Tools 同名按钮）
  await page.locator(".ant-tour-next-btn").click();
  await expect(page.getByText("总览当前岗位")).toBeVisible();

  // 关闭并记忆已读
  await page.locator(".ant-tour .ant-tour-close").click();
  await expect(page.locator(".ant-tour")).toHaveCount(0);
  const seen = await page.evaluate(() =>
    localStorage.getItem("hiro2:tour-seen:recruiting"),
  );
  expect(seen).toBe("1");

  // 问号按钮可重开（即使已读）
  await page.getByRole("button", { name: "使用引导" }).click();
  await expect(page.locator(".ant-tour")).toBeVisible();
});

test("switching workspace opens its own first-visit tour", async ({ page }) => {
  await page.goto("/career/jobs");
  await expect(page.getByText("欢迎来到求职工作区")).toBeVisible();

  await page.goto("/data");
  await expect(page.getByText("欢迎来到数据工作区")).toBeVisible();
});
