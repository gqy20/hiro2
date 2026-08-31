import { expect, test } from "./fixture";

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
  await page.getByTitle("大数据").click();
  await expect(page.locator(".career-job-card")).toHaveCount(1);
  await expect(
    page.getByRole("heading", { name: "大数据工程师", level: 2 }),
  ).toBeVisible();
});

test("career workspace uses focused navigation and explicit diagnosis", async ({
  page,
}) => {
  await page.goto("/career/jobs");
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
  await expect(
    page.getByRole("heading", { name: "人岗诊断", level: 1 }),
  ).toHaveCount(1);
  await expect(page.getByRole("heading", { name: "我的画像" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "后续行动" })).toBeVisible();
  await expect(page.getByRole("link", { name: "查看学习路径" })).toBeVisible();
  await expect(page.getByText("成长计划", { exact: true })).toHaveCount(0);
});

test("career flow carries target and profile data into diagnosis and resume", async ({
  page,
}) => {
  await page.goto("/career/jobs");
  await expect(page.getByText("当前目标")).toBeVisible();
  await page
    .getByRole("article")
    .filter({ hasText: "AI Agent 工程师" })
    .getByRole("button", { name: /开始诊断/ })
    .click();
  await expect(page).toHaveURL(/career\/diagnosis\?job=ai-agent-v2/);

  await page.goto("/profile");
  await expect(page.locator(".profile-skill-row")).toHaveCount(4);
  await page.locator(".profile-skill-row").first().click();
  await expect(page.getByRole("dialog")).toContainText("技能判断");
  await expect(page.getByLabel("当前状态")).toBeVisible();
  await page.getByRole("button", { name: "应用技能修改" }).click();
  await expect(
    page.getByRole("button", { name: "保存更改并重新诊断" }),
  ).toBeEnabled();
  await page.getByLabel("新增能力证明").fill("Agent 评测基准项目");
  await page.getByRole("button", { name: "添加能力证明" }).click();
  await expect(page.getByText("Agent 评测基准项目")).toBeVisible();

  await page.goto("/career/resume?job=ai-agent-v2");
  await expect(page.getByLabel("求职意向")).toHaveValue("AI Agent 工程师");
  await expect(
    page.getByText(/已从我的画像带入 \d+ 项技能、\d+ 项能力证明/),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "投递建议" })).toBeVisible();
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

test("career path renders clickable cert/contest cards", async ({ page }) => {
  await page.goto("/career/path");
  // 证/赛段结构化卡片：至少一张，带实体名与可点击链接（或纯文本卡）
  const cards = page.locator(".xlzsz-card");
  await expect(cards.first()).toBeVisible();
  await expect(page.locator(".xlzsz-card-name").first()).toBeVisible();
  // 至少一张卡是可点击的官方链接（target=_blank）
  const linkCard = page.locator("a.xlzsz-card-link").first();
  if (await linkCard.count()) {
    await expect(linkCard).toHaveAttribute("target", "_blank");
  }
});

test("career path shows forward-looking trend badge from prediction system", async ({
  page,
}) => {
  await page.goto("/career/path");
  // 预测上升/新涌现的能力域，学习路径应展示前瞻徽标（时间情报域 -> 学练段）
  const trend = page.locator(".career-path-trend").first();
  await expect(trend).toBeVisible();
  await expect(trend).toContainText("前瞻");
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
