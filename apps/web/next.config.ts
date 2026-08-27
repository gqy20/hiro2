import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // LAN review uses the host IP; allow its Turbopack resources in dev mode.
  allowedDevOrigins: ["localhost", "127.0.0.1", "10.10.11.153"],
  // e2e 用独立 distDir+端口+mock：避开 dev 单实例锁，与用户 dev server 共存
  ...(process.env.E2E ? { distDir: ".next-e2e" } : {}),
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
