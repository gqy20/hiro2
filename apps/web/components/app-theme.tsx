"use client";

import { ConfigProvider, App as AntApp, type ThemeConfig } from "antd";
import { XProvider } from "@ant-design/x";

const theme: ThemeConfig = {
  token: {
    borderRadius: 4,
    colorBgBase: "#f5f1e8",
    colorBgContainer: "#fffdf8",
    colorBorder: "#cfc8bb",
    colorError: "#dc3c34",
    colorInfo: "#2457e6",
    colorPrimary: "#2457e6",
    colorSuccess: "#17824b",
    colorText: "#20201d",
    colorTextSecondary: "#625f58",
    colorWarning: "#b18b00",
    controlHeight: 34,
    fontFamily: "Inter, Noto Sans SC, PingFang SC, Microsoft YaHei, sans-serif",
    fontSize: 14,
    lineWidth: 1,
  },
  components: {
    Button: { borderRadius: 4, fontWeight: 600 },
    Drawer: { colorBgElevated: "#fffdf8" },
    Table: { headerBg: "#faf8f2", rowHoverBg: "#fff5c8" },
    Tag: { defaultBg: "#faf8f2", defaultColor: "#20201d" },
  },
};

export function AppTheme({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <ConfigProvider theme={theme}>
      <XProvider>
        <AntApp>{children}</AntApp>
      </XProvider>
    </ConfigProvider>
  );
}
