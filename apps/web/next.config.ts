import path from "node:path";

import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // LAN review uses the host IP; allow its Turbopack resources in dev mode.
  allowedDevOrigins: ["localhost", "127.0.0.1", "10.10.11.153"],
  turbopack: {
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
