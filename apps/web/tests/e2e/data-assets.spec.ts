import { expect, test } from "@playwright/test";

test("resume dataset exposes test records and structured detail", async ({
  page,
}) => {
  await page.goto("/data/assets/resumes?tab=records");
  await expect(
    page.getByRole("heading", { name: "简历档案", level: 1 }),
  ).toBeVisible();
  await expect(page.locator(".resume-record-row")).toHaveCount(3);
  await expect(page.getByText("合成测试").first()).toBeVisible();

  await page.locator(".resume-record-row").first().click();
  await expect(page.getByText("合成测试简历")).toBeVisible();
  await expect(page.getByRole("tab", { name: "结构化画像" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "文档预览" })).toBeVisible();
  await expect(page.getByRole("tab", { name: "处理信息" })).toBeVisible();
});
