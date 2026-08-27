import { expect, test } from "@playwright/test";

test("adds / edits / removes project with audit trail", async ({ page }) => {
  await page.goto("/diagnosis");

  const newInput = page.getByLabel("新增项目");
  await newInput.fill("e2e 新增项目");
  await page.getByRole("button", { name: "新增" }).click();
  await expect(page.getByText("e2e 新增项目")).toBeVisible();
  await expect(page.locator(".project-audit-meta")).toContainText(
    "已记录 1 条",
  );

  const editButtons = page.getByRole("button", { name: /^编辑项目 proj-/ });
  await editButtons.first().click();
  const editInput = page.locator(".project-row-editing input").first();
  await editInput.fill("e2e 编辑项目");
  await page.locator(".project-row-editing button.ant-btn-primary").click();
  await expect(page.getByText("e2e 编辑项目")).toBeVisible();
  await expect(page.locator(".project-audit-meta")).toContainText(
    "已记录 2 条",
  );

  const deleteButtons = page.getByRole("button", { name: /^删除项目 proj-/ });
  const total = await deleteButtons.count();
  await deleteButtons.nth(total - 1).click();
  await expect(page.locator(".project-audit-meta")).toContainText(
    "已记录 3 条",
  );
});

test("recalculates score after click", async ({ page }) => {
  await page.goto("/diagnosis");

  const meter = page.locator(".confidence-meter-prominent").first();
  const scoreBefore = await meter.getAttribute("aria-label");
  expect(scoreBefore).not.toBeNull();

  await page.getByRole("button", { name: "重新计算" }).click();
  await page.waitForTimeout(800);

  const scoreAfter = await meter.getAttribute("aria-label");
  expect(scoreAfter).not.toBeNull();
  expect(scoreAfter).toMatch(/%/);
});

test("renders empty and error variants", async ({ page }) => {
  await page.goto("/diagnosis?state=empty");
  await expect(page.getByText("上传简历或录入技能后开始诊断。")).toBeVisible();

  await page.goto("/diagnosis?state=error");
  await expect(
    page.getByText("候选人或岗位版本数据暂时不可用。"),
  ).toBeVisible();
});
