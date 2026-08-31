// 共享 e2e fixture：默认预置"引导已读"，避免首访 Tour 遮罩拦截各业务用例的点击。
// 引导层自身的行为由 onboarding.spec.ts 覆盖（它显式清除已读标记）。
import { test as base } from "@playwright/test";

export const test = base.extend({
  // 参数名用 apply 而非 use：避免 react-hooks 规则把 Playwright 回调误判为 Hook
  page: async ({ page }, apply) => {
    await page.addInitScript(() => {
      localStorage.setItem("hiro2:tour-seen:recruiting", "1");
      localStorage.setItem("hiro2:tour-seen:career", "1");
      localStorage.setItem("hiro2:tour-seen:data", "1");
    });
    await apply(page);
  },
});

export { expect } from "@playwright/test";
