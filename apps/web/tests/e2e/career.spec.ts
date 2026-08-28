import { expect, test } from "@playwright/test";

test("career jobs page renders published job cards and group filter", async ({
  page,
}) => {
  await page.goto("/career/jobs");

  await expect(
    page.getByRole("heading", { name: "目标岗位", level: 1 }),
  ).toBeVisible();
  await expect(page.locator(".career-job-card")).toHaveCount(4);
  await expect(
    page.getByRole("heading", { name: "AI Agent 工程师", level: 2 }),
  ).toBeVisible();

  // 岗位族筛选：选中「大数据」后只保留一张卡
  await page.getByText("大数据", { exact: true }).click();
  await expect(page.locator(".career-job-card")).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: "大数据工程师", level: 2 }),
  ).toBeVisible();
});

test("career home renders ready state and empty state", async ({ page }) => {
  await page.goto("/career");
  await expect(
    page.getByRole("heading", { name: /AI 应用工程师/, level: 1 }),
  ).toBeVisible();
  await expect(page.getByText("必备能力")).toBeVisible();

  await page.goto("/career?state=empty");
  await expect(
    page.getByRole("heading", { name: "开始你的成长诊断", level: 1 }),
  ).toBeVisible();
  await expect(
    page.locator(".career-next-action strong"),
  ).toContainText("选择目标岗位");
  await expect(
    page.locator(".career-progress-card strong"),
  ).toContainText("上传简历开始诊断");
});

test("career path page renders gaps with learn-practice-evaluate-certify steps", async ({
  page,
}) => {
  await page.goto("/career/path");

  await expect(
    page.getByRole("heading", { name: "学习路径", level: 1 }),
  ).toBeVisible();
  const items = page.locator(".career-path-item");
  await expect(items.first()).toBeVisible();
  // 学练赛证：每项缺口至少渲染「学」段
  await expect(
    page.locator(".career-path-steps li").first(),
  ).toBeVisible();
});
