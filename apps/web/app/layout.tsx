import type { Metadata } from "next";
import { AntdRegistry } from "@ant-design/nextjs-registry";
import { Archivo_Narrow, IBM_Plex_Mono, Inter } from "next/font/google";

import { AppTheme } from "@/components/app-theme";
import "./globals.css";

// 西文/数字字体自托管：next/font 构建期内嵌字体文件，不依赖用户系统安装。
// 中文不打包（体积太大），继续走系统栈（Noto Sans SC / PingFang SC / Microsoft YaHei）。
const inter = Inter({ subsets: ["latin"], variable: "--font-inter" });
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-plex-mono",
});
const archivoNarrow = Archivo_Narrow({
  subsets: ["latin"],
  variable: "--font-archivo-narrow",
});

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
    <html
      className={`${inter.variable} ${plexMono.variable} ${archivoNarrow.variable}`}
      lang="zh-CN"
    >
      <body>
        <AntdRegistry>
          <AppTheme>{children}</AppTheme>
        </AntdRegistry>
      </body>
    </html>
  );
}
