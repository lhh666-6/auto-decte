import type { ReactNode } from "react";
import { NavLink, useNavigate } from "react-router-dom";

import { useWebSession } from "./WebSessionProvider";
import type { WorkspaceRole } from "./types";
import "./web-workspaces.css";

const NAVIGATION: Record<WorkspaceRole, {
  label: string;
  links: Array<{ to: string; label: string }>;
}> = {
  PLANT_MANAGER: {
    label: "厂长工作区导航",
    links: [
      { to: "/plant/overview", label: "本厂概览" },
      { to: "/plant/notifications", label: "通知与知悉" },
      { to: "/plant/forms", label: "表单查询" },
      { to: "/plant/workflows", label: "流程查询" },
      { to: "/plant/production", label: "生产看板" },
      { to: "/plant/employees", label: "生产与员工" },
      { to: "/plant/exceptions", label: "异常处理" },
      { to: "/plant/payroll", label: "工资查询" },
    ],
  },
  FINANCE: {
    label: "财务工作区导航",
    links: [
      { to: "/finance/position-data", label: "岗位数据" },
      { to: "/finance/payroll", label: "工资数据" },
      { to: "/finance/payroll-rules", label: "业务预设" },
      { to: "/finance/exports", label: "导出历史" },
      // V1 暂缓: 财务概览, 今日提交, 月度统计, 年度统计, 异常记录, 表单查询, 工作流管理, 业务建模, 报表模板
    ],
  },
  ADMIN: {
    label: "管理工作区导航",
    links: [
      { to: "/admin/overview", label: "业务全景" },
      { to: "/admin/organization", label: "组织与员工" },
      { to: "/admin/factories", label: "工厂与岗位" },
      { to: "/admin/audit", label: "审计记录" },
      // V1 暂缓: 角色权限, 表单审批, 流程审批, 工资审批, 版本异常, 报表模板, 智能服务, 通知管理
    ],
  },
};

export function WorkspaceShell({
  workspace,
  children,
}: {
  workspace: WorkspaceRole;
  children: ReactNode;
}) {
  const { session, logout } = useWebSession();
  const navigate = useNavigate();
  const navigation = NAVIGATION[workspace];

  async function signOut() {
    await logout();
    navigate("/login", { replace: true });
  }

  return (
    <div className="web-workspace-shell">
      <header className="web-workspace-header">
        <strong>工业工资表系统</strong>
        <div className="web-session-identity">
          <span>{session?.employee_name}</span>
          {session?.factory_name && <span>{session.factory_name}</span>}
          <button type="button" onClick={() => void signOut()}>退出</button>
        </div>
      </header>
      <aside className="web-workspace-sidebar">
        <nav aria-label={navigation.label}>
          {navigation.links.map((link) => (
            <NavLink key={link.to} to={link.to}>
              {link.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="web-workspace-content">{children}</main>
    </div>
  );
}
