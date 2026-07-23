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
      { to: "/finance/overview", label: "财务概览" },
      { to: "/finance/today", label: "今日提交" },
      { to: "/finance/month", label: "月度统计" },
      { to: "/finance/year", label: "年度统计" },
      { to: "/finance/exceptions", label: "异常记录" },
      { to: "/finance/forms", label: "表单查询" },
      { to: "/finance/workflows", label: "工作流管理" },
      { to: "/finance/business-modeling", label: "业务建模" },
      { to: "/finance/payroll-rules", label: "工资规则" },
      { to: "/finance/report-templates", label: "报表模板" },
      { to: "/finance/exports", label: "报表导出" },
    ],
  },
  ADMIN: {
    label: "管理工作区导航",
    links: [
      { to: "/admin/overview", label: "系统概览" },
      { to: "/admin/organization", label: "组织架构" },
      { to: "/admin/roles", label: "角色权限" },
      { to: "/admin/form-approvals", label: "表单审批" },
      { to: "/admin/workflow-approvals", label: "流程审批" },
      { to: "/admin/payroll-approvals", label: "工资审批" },
      { to: "/admin/version-exceptions", label: "版本异常" },
      { to: "/admin/report-templates", label: "报表模板" },
      { to: "/admin/integrations/deepseek", label: "智能服务" },
      { to: "/admin/notifications", label: "通知管理" },
      { to: "/admin/audit", label: "审计日志" },
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
