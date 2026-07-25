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
      { to: "/plant/production", label: "本厂生产" },
      { to: "/plant/forms", label: "本厂业务表单" },
      { to: "/plant/exceptions", label: "质量与异常" },
      { to: "/plant/employees", label: "人员调度" },
      { to: "/plant/overview", label: "本厂概览" },
    ],
  },
  FINANCE: {
    label: "财务工作区导航",
    links: [
      { to: "/finance/position-data", label: "岗位数据" },
      { to: "/finance/payroll", label: "工资核算" },
      { to: "/finance/payroll-rules", label: "业务预设" },
      { to: "/finance/exports", label: "导出历史" },
    ],
  },
  ADMIN: {
    label: "管理工作区导航",
    links: [
      { to: "/admin/overview", label: "业务全景" },
      { to: "/admin/business-forms", label: "正式业务表单" },
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
