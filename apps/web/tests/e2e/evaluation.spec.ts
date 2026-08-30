import { expect, test } from "@playwright/test";

test("prediction errors use business labels and expose concrete cases", async ({
  page,
}) => {
  await page.goto("/evaluation");

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
