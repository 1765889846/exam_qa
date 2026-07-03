import { NavLink, Outlet } from "react-router-dom";
import { HealthBadge } from "@/features/health/HealthBadge";
import { ThemeToggle } from "@/components/ThemeToggle";

export function AppLayout() {
  return (
    <div className="exam-shell">
      <a href="#main-content" className="exam-skip-link">
        跳到主内容
      </a>
      <header className="exam-shell__header">
        <h1 className="exam-shell__title">RAG 复习助手</h1>
        <span className="exam-shell__course">信号与系统</span>
        <span className="exam-shell__spacer" />
        <nav className="exam-shell__nav" aria-label="主导航">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `exam-shell__nav-link${isActive ? " exam-shell__nav-link--active" : ""}`
            }
          >
            工作台
          </NavLink>
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `exam-shell__nav-link${isActive ? " exam-shell__nav-link--active" : ""}`
            }
          >
            设置
          </NavLink>
        </nav>
        <ThemeToggle />
        <HealthBadge />
      </header>
      <main id="main-content" className="exam-shell__main">
        <Outlet />
      </main>
    </div>
  );
}
