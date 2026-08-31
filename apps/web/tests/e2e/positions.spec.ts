import { expect, test } from "./fixture";

test("positions renders detected changes without NaN or undefined", async ({
  page,
}) => {
  await page.goto("/positions");

  const section = page.locator(".positions-detected");
  await expect(section).toBeVisible();
  await expect(section).toContainText("项待复核");
  await expect(section.locator(".detected-item").first()).toBeVisible();

  const text = (await section.innerText()) ?? "";
  expect(text).not.toContain("NaN");
  expect(text).not.toContain("undefined");

  // 岗位名与份额变化使用真实字段渲染（snake_case VM 契约）
  await expect(section.getByText(/条 JD ·/).first()).toBeVisible();
  await expect(section.locator(".detected-tag").first()).toBeVisible();
});
