import { expect, test } from "@playwright/test";

test("accepts all changes and publishes target version", async ({ page }) => {
  await page.goto("/jobs");

  // 分组渲染下接受按钮可能分批出现，循环点击直到审核队列清零
  for (let i = 0; i < 20; i++) {
    const btn = page.getByRole("button", { name: /^接受 / }).first();
    if (!(await btn.isVisible())) break;
    await btn.click();
  }
  await expect(page.getByText("0 条待处理")).toBeVisible();

  await page.getByRole("button", { name: "发布版本" }).click();
  await expect(page.getByText("发布岗位版本")).toBeVisible();

  await page.getByRole("button", { name: /^发布 v/ }).click();

  await expect(
    page.getByRole("heading", { name: "岗位版本已发布" }),
  ).toBeVisible({ timeout: 15_000 }); // dev server 首次编译发布视图较慢
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
  // mock 模式下 ?state=error 渲染组件内错误视图（real 模式走路由级 error.tsx）
  await expect(page.getByText("岗位版本数据暂时不可用")).toBeVisible();
});
