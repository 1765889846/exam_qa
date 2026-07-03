import { ConfigProvider, theme } from "antd";
import zhCN from "antd/locale/zh_CN";
import { type ReactNode } from "react";
import { ThemeContextProvider, useTheme } from "@/lib/ThemeContext";
import { antDarkTokens, antLightTokens } from "@/styles/theme";

function AntThemeBridge({ children }: { children: ReactNode }) {
  const { isDark } = useTheme();

  return (
    <ConfigProvider
      locale={zhCN}
      theme={{
        algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
        token: isDark ? antDarkTokens : antLightTokens,
      }}
    >
      {children}
    </ConfigProvider>
  );
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  return (
    <ThemeContextProvider>
      <AntThemeBridge>{children}</AntThemeBridge>
    </ThemeContextProvider>
  );
}
