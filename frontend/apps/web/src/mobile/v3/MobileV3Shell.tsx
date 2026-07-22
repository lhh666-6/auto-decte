import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useMobileSession } from "../session/MobileSessionProvider";
import { MobileV3Icon } from "./MobileV3Icon";

const MOBILE_V3_NAV = [
  { to: "/mobile/home", label: "首页", icon: "home" },
  { to: "/mobile/work", label: "记录工作", icon: "work" },
  { to: "/mobile/submissions", label: "提交记录", icon: "submissions" },
  { to: "/mobile/profile", label: "我的", icon: "profile" },
] as const;

export function MobileV3Shell() {
  const location = useLocation();
  const { status, sessionMetadata } = useMobileSession();
  const isLogin = location.pathname === "/mobile/login";
  const role = sessionMetadata?.bamboo_role ?? "";
  const showProductionNav = !isLogin && status === "authenticated" && Boolean(role) && role !== "FINANCE_APPROVER";

  return (
    <div className="mobile-app-shell mobile-v3-shell" data-mobile-shell="v3">
      <main className="mobile-content">
        <Outlet />
      </main>
      {showProductionNav && (
        <nav className="mobile-bottom-nav" aria-label="移动端导航">
          {MOBILE_V3_NAV.map((item) => {
            const current = location.pathname === item.to
              || (item.to === "/mobile/work" && location.pathname.startsWith("/mobile/records/"));
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={`mobile-nav-item${current ? " active" : ""}`}
                aria-current={current ? "page" : undefined}
              >
                <span className="mobile-nav-icon"><MobileV3Icon name={item.icon} /></span>
                <span className="mobile-nav-label">{item.label}</span>
              </NavLink>
            );
          })}
        </nav>
      )}
    </div>
  );
}
