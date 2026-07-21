import { NavLink, Outlet, useLocation } from "react-router-dom";

const MOBILE_NAV = [
  { to: "/mobile/home", label: "首页", icon: "🏠" },
  { to: "/mobile/record", label: "记录工作", icon: "📝" },
  { to: "/mobile/drafts", label: "草稿", icon: "📄" },
  { to: "/mobile/submissions", label: "提交记录", icon: "📋" },
  { to: "/mobile/profile", label: "我的", icon: "👤" },
] as const;

/**
 * Mobile layout with bottom tab navigation.
 * Wraps all /mobile/* routes.
 */
export function MobileLayout() {
  const location = useLocation();

  // Hide bottom nav on login page
  const isLogin = location.pathname === "/mobile/login";

  return (
    <div className="mobile-app-shell">
      <main className="mobile-content">
        <Outlet />
      </main>
      {!isLogin && (
        <nav className="mobile-bottom-nav" aria-label="移动端导航">
          {MOBILE_NAV.map((item) => {
            const current = location.pathname.startsWith(item.to);
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={`mobile-nav-item${current ? " active" : ""}`}
                aria-current={current ? "page" : undefined}
              >
                <span className="mobile-nav-icon">{item.icon}</span>
                <span className="mobile-nav-label">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      )}
    </div>
  );
}
