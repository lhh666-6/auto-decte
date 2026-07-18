import { NavLink, Outlet, useLocation } from "react-router-dom";
import type { MouseEvent } from "react";

const PRIMARY_NAV = [
  { to: "/workbench/review", label: "审核工作台", prefix: "/workbench" },
  { to: "/templates", label: "模板中心", prefix: "/templates" },
  { to: "/master-data/employees", label: "基础数据", prefix: "/master-data" },
  { to: "/exports", label: "导出数据", prefix: "/exports" },
] as const;

export function AppShell() {
  const location = useLocation();

  function confirmNavigation(event: MouseEvent<HTMLAnchorElement>) {
    if (event.currentTarget.pathname === location.pathname) return;
    const beforeUnload = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(beforeUnload);
    if (
      beforeUnload.defaultPrevented &&
      !window.confirm("当前有尚未保存的审核修改，确定离开吗？")
    ) {
      event.preventDefault();
    }
  }

  return (
    <div className="routed-app-shell">
      <header className="global-app-header">
        <strong className="global-product-name">工业工资表系统</strong>
        <nav aria-label="一级导航">
          {PRIMARY_NAV.map((item) => {
            const current = location.pathname.startsWith(item.prefix);
            return (
              <NavLink
                key={item.to}
                to={item.to}
                aria-current={current ? "page" : undefined}
                onClick={confirmNavigation}
              >
                {item.label}
              </NavLink>
            );
          })}
        </nav>
        <div className="global-context">
          <span><i className="connection-dot" /> 本地单机模式 · 服务正常</span>
        </div>
      </header>
      <main className="routed-app-content">
        <Outlet />
      </main>
    </div>
  );
}
