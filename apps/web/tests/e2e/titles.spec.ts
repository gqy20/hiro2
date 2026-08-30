import { expect, test } from "@playwright/test";

type RouteTitle = {
  path: string;
  title: string;
  heading?: string;
};

const GROUPS: Array<{ name: string; routes: RouteTitle[] }> = [
  {
    name: "招聘",
    routes: [
      { path: "/", title: "工作台" },
      { path: "/new-jobs", title: "岗位发现" },
      { path: "/positions", title: "我的岗位" },
      { path: "/skills", title: "能力全景" },
      { path: "/diagnosis", title: "候选诊断" },
    ],
  },
  {
    name: "求职",
    routes: [
      { path: "/career/jobs", title: "目标岗位" },
      { path: "/profile", title: "我的画像" },
      { path: "/career/diagnosis", title: "人岗诊断" },
      { path: "/career/path", title: "学习路径" },
      { path: "/career/resume", title: "简历工作台" },
    ],
  },
  {
    name: "数据",
    routes: [
      { path: "/data", title: "总览" },
      { path: "/data/assets", title: "数据资产" },
      {
        path: "/data/assets/resumes?tab=records",
        title: "数据集档案",
        heading: "简历档案",
      },
      { path: "/tasks", title: "证据审核" },
      { path: "/evaluation", title: "评测质量" },
    ],
  },
  {
    name: "趋势洞察",
    routes: [{ path: "/temporal", title: "趋势洞察" }],
  },
];

for (const group of GROUPS) {
  test(`${group.name}页面使用统一标题契约`, async ({ page }) => {
    test.setTimeout(120_000);
    for (const route of group.routes) {
      await page.goto(route.path);
      await expect(page).toHaveTitle(`${route.title} | Hiro2`);
      const headings = page.locator("h1");
      await expect(headings).toHaveCount(1);
      if (route.path !== "/diagnosis" || route.heading) {
        await expect(headings).toHaveText(route.heading ?? route.title);
      }
    }
  });
}
