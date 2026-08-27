import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  expect: { timeout: 5_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3100",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  webServer: {
    command: "pnpm dev",
    url: "http://localhost:3100",
    // 独立端口 + 强制 mock：e2e 保持密闭，不受 apps/web/.env 的 real 模式
    // 与 8000 端口 API 新旧影响，也不复用用户手动起的 3000 dev server
    reuseExistingServer: false,
    timeout: 60_000,
    env: {
      ...process.env,
      PORT: "3100",
      E2E: "1",
      NEXT_PUBLIC_USE_MOCK: "true",
    },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
