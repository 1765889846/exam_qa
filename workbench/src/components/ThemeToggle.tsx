import { useTheme } from "@/lib/ThemeContext";

export function ThemeToggle() {
  const { isDark, toggle } = useTheme();

  return (
    <button
      type="button"
      className="exam-theme-toggle"
      onClick={toggle}
      aria-label={isDark ? "切换为亮色模式" : "切换为暗色模式"}
      title={isDark ? "亮色模式" : "暗色模式"}
    >
      <span className="exam-theme-toggle__icon" aria-hidden="true">
        {isDark ? "☀" : "☾"}
      </span>
      <span className="exam-theme-toggle__label">{isDark ? "亮色" : "暗色"}</span>
    </button>
  );
}
