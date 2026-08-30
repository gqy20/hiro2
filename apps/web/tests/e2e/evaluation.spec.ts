import { expect, test } from "@playwright/test";

test("evaluation datasets switch metrics and expose concrete cases", async ({
  page,
}) => {
  await page.goto("/evaluation");

  await expect(page.getByRole("heading", { name: "岗位映射" })).toBeVisible();
  await expect(page.getByText("78%")).toBeVisible();

  await page.getByRole("button", { name: /领域判定.*50 样本/ }).click();
  await expect(page.getByRole("heading", { name: "领域判定" })).toBeVisible();
  await expect(page.getByText("项目资料员")).toBeVisible();
  await page.getByText("项目资料员").click();
  await expect(page.getByRole("dialog")).toContainText("需重新确认岗位范围");
  await page.keyboard.press("Escape");

  await page.getByRole("button", { name: /趋势回测.*9 样本/ }).click();
  await expect(page.getByRole("heading", { name: "预测偏差" })).toBeVisible();
  await expect(page.getByText("预测上升，实际下降").first()).toBeVisible();
  await expect(page.getByText("flat->down")).toHaveCount(0);

  await page
    .getByRole("button", { name: /预测上升，实际下降.*严重偏差/ })
    .click();
  await expect(page.getByRole("dialog")).toContainText("1 条回测记录");
  await expect(page.getByRole("dialog")).toContainText("实际下降");
  await expect(page.getByRole("dialog")).toContainText("置信度");
});
