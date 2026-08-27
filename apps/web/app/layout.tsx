import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";

import { AppTheme } from "@/components/app-theme";
import "./globals.css";

// 生产数据来自 API，避免构建期预渲染依赖尚未初始化的数据库。
export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Hiro2 | 岗位更新",
  description: "证据驱动的岗位能力演化工作台",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body>
        <AntdRegistry>
          <AppTheme>{children}</AppTheme>
        </AntdRegistry>
      </body>
    </html>
  );
}
