import { NavLink, Outlet, useLocation } from "react-router-dom";

import { useMobileSession } from "../session/MobileSessionProvider";
import { useBambooSystemNotifications } from "../notifications/useBambooSystemNotifications";
import { MobileV3Icon } from "./MobileV3Icon";

const MOBILE_V3_NAV = [
  { to: "/mobile/home", label: "首页", icon: "home" },
  { to: "/mobile/work", label: "记录工作", icon: "work" },
  { to: "/mobile/submissions", label: "提交记录", icon: "submissions" },
  { to: "/mobile/profile", label: "我的", icon: "profile" },
] as const;

const PAGE_COPY: Array<{ match: (path: string) => boolean; title: string; sub: string }> = [
  { match: (path) => path === "/mobile/home", title: "竹丝工序记录", sub: "完成工作后主动记录" },
  { match: (path) => path === "/mobile/work", title: "记录工作", sub: "上游完成后，本环节才可以处理" },
  { match: (path) => path.startsWith("/mobile/records/"), title: "竹丝流程详情", sub: "查看整张电子表单并完成当前签字" },
  { match: (path) => path === "/mobile/submissions", title: "提交记录", sub: "查看本人提交与后续流转状态" },
  { match: (path) => path === "/mobile/profile", title: "我的", sub: "账号、班组与应用状态" },
  { match: (path) => path === "/mobile/personnel", title: "人员调度", sub: "厂长审批与管理员执行" },
];

export function MobileV3Shell() {
  const location = useLocation();
  const { status, sessionMetadata } = useMobileSession();
  const isLogin = location.pathname === "/mobile/login";
  const role = sessionMetadata?.bamboo_role ?? "";
  const showProductionShell = !isLogin && status === "authenticated" && Boolean(role) && role !== "FINANCE_APPROVER";
  useBambooSystemNotifications(sessionMetadata?.employee_code, showProductionShell);
  const pageCopy = PAGE_COPY.find((item) => item.match(location.pathname)) ?? PAGE_COPY[0];

  return (
    <div className="mobile-app-shell mobile-v3-shell" data-mobile-shell="v3">
      {showProductionShell && (
        <header className="mobile-v3-topbar topbar">
          <div className="topbar-row">
            <div>
              <div className="brand-title">{pageCopy.title}</div>
              <div className="brand-sub">{pageCopy.sub}</div>
            </div>
            <span className="net">在线</span>
          </div>
        </header>
      )}
      <main className="mobile-content">
        <Outlet />
      </main>
      {showProductionShell && (
        <nav className="bottom-nav mobile-bottom-nav" aria-label="移动端导航">
          {MOBILE_V3_NAV.map((item) => {
            const current = location.pathname === item.to
              || (item.to === "/mobile/work" && location.pathname.startsWith("/mobile/records/"));
            return (
              <NavLink
                key={item.to}
                to={item.to}
                className={`nav-btn mobile-nav-item${current ? " on active" : ""}`}
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
