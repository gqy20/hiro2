import { expect, test } from "@playwright/test";

test("renders graph, selects capability, switches to point", async ({ page }) => {
  await page.goto("/skills");

  await expect(page.locator(".graph-node")).toHaveCount(41);
  await expect(page.locator(".skill-graph-counts dd")).toContainText("41 / 41");

  await page
    .locator("[data-capability-id='cap_04'][data-point-name='']")
    .click();
  await expect(
    page.getByRole("heading", { name: "AI Agent", level: 3 }),
  ).toBeVisible();
  await expect(page.locator(".skill-node-detail-link")).toHaveCount(5);

  await page.getByRole("button", { name: "MCP" }).first().click();
  await expect(
    page.getByRole("heading", { name: "MCP", level: 3 }),
  ).toBeVisible();
  await expect(page.locator(".skill-node-detail-link")).toHaveCount(5);
});

test("toolbar shows 3 filter selects and counts visible nodes", async ({ page }) => {
  await page.goto("/skills");

  // 3 个筛选 Select（技术栈 / 级别 / 能力类型）+ 清除按钮
  const toolbar = page.locator(".skill-graph-toolbar");
  await expect(toolbar.locator(".ant-select")).toHaveCount(3);
  await expect(
    toolbar.getByRole("button", { name: "清除筛选" }),
  ).toBeVisible();

  // 计数显示
  await expect(page.locator(".skill-graph-counts dd")).toContainText("41 / 41");
});

test("renders empty and error variants", async ({ page }) => {
  await page.goto("/skills?state=empty");
  await expect(page.getByText("当前图谱暂无可用技能点。")).toBeVisible();

  await page.goto("/skills?state=error");
  await expect(page.getByText("技能图谱数据暂时不可用")).toBeVisible();
});