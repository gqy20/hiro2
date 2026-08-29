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

test("career workspace redirects to focused navigation and explicit diagnosis", async ({
  page,
}) => {
  await page.goto("/career");
  await expect(page).toHaveURL(/\/career\/jobs$/);
  await expect(
    page.getByRole("button", { name: "求职", pressed: true }),
  ).toBeVisible();
  const nav = page.getByRole("navigation", { name: "主导航" });
  await expect(nav.getByRole("link")).toHaveCount(5);
  await expect(nav.getByRole("link", { name: "人岗诊断" })).toBeVisible();
  await expect(nav.getByText("求职成长", { exact: true })).toHaveCount(0);
  await expect(nav.getByText("候选诊断", { exact: true })).toHaveCount(0);

  await Promise.all([
    page.waitForURL(/\/career\/diagnosis$/, { timeout: 20_000 }),
    nav.getByRole("link", { name: "人岗诊断" }).click(),
  ]);
  await expect(page.getByRole("heading", { name: "我的画像" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "后续行动" })).toBeVisible();
  await expect(page.getByRole("link", { name: "查看学习路径" })).toBeVisible();
  await expect(page.getByText("成长计划", { exact: true })).toHaveCount(0);
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
  await expect(page.locator(".career-path-steps li").first()).toBeVisible();
});

test("career jobs and path render empty and error variants", async ({
  page,
}) => {
  await page.goto("/career/jobs?state=empty");
  await expect(page.getByText("暂无已发布岗位版本。")).toBeVisible();

  await page.goto("/career/jobs?state=error");
  await expect(
    page.getByText("岗位数据暂时不可用，请稍后重试。"),
  ).toBeVisible();

  await page.goto("/career/path?state=empty");
  await expect(
    page.getByText("选择目标岗位并完成诊断后生成学习路径。"),
  ).toBeVisible();

  await page.goto("/career/path?state=error");
  await expect(
    page.getByText("学习路径数据暂时不可用，请稍后重试。"),
  ).toBeVisible();
});
