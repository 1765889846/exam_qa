/** Ant Design token 映射，与 tokens.css 双主题对齐。 */
export const antLightTokens = {
  colorPrimary: "#0969da",
  colorSuccess: "#1a7f37",
  colorError: "#cf222e",
  colorBgBase: "#ffffff",
  colorBgContainer: "#f6f8fa",
  colorBorder: "#d0d7de",
  colorText: "#1f2328",
  colorTextSecondary: "#656d76",
  borderRadius: 8,
} as const;

export const antDarkTokens = {
  colorPrimary: "#58a6ff",
  colorSuccess: "#3fb950",
  colorError: "#f85149",
  colorBgBase: "#0d1117",
  colorBgContainer: "#161b22",
  colorBorder: "#30363d",
  colorText: "#c9d1d9",
  colorTextSecondary: "#8b949e",
  borderRadius: 8,
} as const;
