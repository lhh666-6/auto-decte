import { useEffect, useState, useMemo } from "react";

import { listPlantRoleOptions } from "./api";
import { ErrorAlert, PageHeader } from "./shared/SummaryCardGrid";
import type { DataColumn } from "./shared/GovernedDataTable";

interface RoleEntry {
  role_code: string;
  display_name: string;
  category: "web-workspace" | "bamboo-production";
  scope: string;
  permissions: string;
}

/** §6.2 — Web 工作区角色定义 */
const WEB_WORKSPACE_ROLES: RoleEntry[] = [
  {
    role_code: "ADMIN",
    display_name: "系统管理员",
    category: "web-workspace",
    scope: "全局",
    permissions: "表单/流程/工资审批、组织架构、角色权限、审计日志、通知管理、报表模板上传",
  },
  {
    role_code: "FINANCE",
    display_name: "财务专员",
    category: "web-workspace",
    scope: "财务工作区",
    permissions: "表单查询与定义、流程管理、业务建模、工资规则配置、报表模板/映射/导出",
  },
  {
    role_code: "PLANT_MANAGER",
    display_name: "厂长",
    category: "web-workspace",
    scope: "本厂",
    permissions: "本厂概览、通知知悉、表单/流程查询、生产看板与签名、员工与调动、异常处理、工资查询",
  },
];

/** Permission pages visible per role */
const ROLE_VISIBLE_PAGES: Record<string, string[]> = {
  ADMIN: ["全站所有页面", "审计日志", "通知管理"],
  FINANCE: ["财务概览", "实时财务账本", "异常记录", "电子表单设计", "报表模板与映射", "正式报表导出", "工资规则与试算"],
  PLANT_MANAGER: ["工厂概览", "通知知悉", "审核工作台", "生产看板", "员工与调动", "异常处理", "工资查询"],
};

/** Submittable processes per role */
const ROLE_PROCESSES: Record<string, string[]> = {
  ADMIN: ["表单管理", "流程管理", "工资审批"],
  FINANCE: ["财务表单设计", "报表映射", "工资规则配置", "正式导出"],
  PLANT_MANAGER: ["表单查询", "流程查询", "异常处理"],
};

export function AdminRolesPage() {
  const [bambooRoles, setBambooRoles] = useState<
    Array<{ role_code: string; display_name: string }>
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedRole, setSelectedRole] = useState<RoleEntry | null>(null);

  useEffect(() => {
    setLoading(true);
    listPlantRoleOptions()
      .then((result) => setBambooRoles(result.items))
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : "岗位数据加载失败"),
      )
      .finally(() => setLoading(false));
  }, []);

  const bambooRoleEntries: RoleEntry[] = bambooRoles.map((r) => ({
    role_code: r.role_code,
    display_name: r.display_name,
    category: "bamboo-production" as const,
    scope: "本厂",
    permissions: "移动端表单填写、生产流程操作（按岗位分工）",
  }));

  const allRoles = [...WEB_WORKSPACE_ROLES, ...bambooRoleEntries];

  /** Compute what pages/processes a role gains or loses compared to baseline (nobody) */
  const impactInfo = useMemo(() => {
    if (!selectedRole) return null;
    const pages = ROLE_VISIBLE_PAGES[selectedRole.role_code] ?? [];
    const processes = ROLE_PROCESSES[selectedRole.role_code] ?? [];
    const factoryScope = selectedRole.scope === "全局"
      ? "所有工厂"
      : selectedRole.scope === "本厂"
        ? "当前工厂"
        : selectedRole.scope;
    return {
      pages,
      processes,
      factoryScope,
      isWebRole: selectedRole.category === "web-workspace",
    };
  }, [selectedRole]);

  function tid(suffix: string): string {
    return `admin-roles-${suffix}`;
  }

  const columns: DataColumn<RoleEntry>[] = [
    {
      key: "category",
      header: "类型",
      render: (row) => (
        <span className={`role-category-badge role-category-${row.category}`} data-testid={tid(`category-${row.role_code}`)}>
          <span aria-hidden="true" className="role-category-icon">
            {row.category === "web-workspace" ? "◈" : "◆"}
          </span>
          {" "}
          {row.category === "web-workspace" ? "Web 工作区" : "Bamboo 生产"}
        </span>
      ),
    },
    {
      key: "code",
      header: "角色编号",
      render: (row) => row.role_code,
    },
    {
      key: "name",
      header: "角色名称",
      render: (row) => (
        <span className="role-name-cell" data-testid={tid(`name-${row.role_code}`)}>
          {row.display_name}
        </span>
      ),
    },
    {
      key: "scope",
      header: "权限范围",
      render: (row) => row.scope,
    },
    {
      key: "permissions",
      header: "权限说明",
      render: (row) => row.permissions,
    },
  ];

  return (
    <section className="admin-roles-page" data-testid={tid("page")}>
      <PageHeader
        title="角色权限"
        subtitle="区分 Web 工作区角色和 Bamboo 生产岗位。修改权限需通过访问档案接口操作。"
      />

      {/* §6.2.1 — 不可组合非法角色提示 */}
      <div className="role-illegal-notice" data-testid={tid("illegal-notice")}>
        <span className="role-illegal-notice-icon" aria-hidden="true">&#9888;</span>
        <span>
          系统管理员、财务、厂长、工人不能通过前端组合出未被后端支持的非法角色。
        </span>
      </div>

      {error && <ErrorAlert message={error} />}

      {loading ? (
        <div role="status" className="empty-state" data-testid={tid("loading")}>加载角色数据中…</div>
      ) : (
        <>
          <div className="governed-table-wrap" data-testid={tid("table")}>
            <table className="governed-table">
              <thead>
                <tr>
                  {columns.map((col) => (
                    <th key={col.key}>{col.header}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {allRoles.map((row) => (
                  <tr
                    key={`${row.category}:${row.role_code}`}
                    className={`governed-table-row-clickable ${selectedRole?.role_code === row.role_code && selectedRole?.category === row.category ? "governed-row--selected" : ""}`}
                    onClick={() => setSelectedRole(row)}
                    data-testid={tid(`row-${row.role_code}`)}
                  >
                    {columns.map((col) => (
                      <td key={col.key}>{col.render(row)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* §6.2.2 — 权限影响预览 */}
          {impactInfo && (
            <div className="role-permission-impact" data-testid={tid("impact-preview")}>
              <h3 className="role-impact-title">
                {impactInfo.isWebRole ? "◈" : "◆"} 选中角色：{selectedRole?.display_name} 的权限影响预览
              </h3>
              <div className="role-impact-list">
                <div className="role-impact-item">
                  <span className="role-impact-arrow">&#8594;</span>
                  <strong>新增可见页面：</strong>
                  <span className="role-impact-gain">
                    {impactInfo.pages.length > 0 ? impactInfo.pages.join("、") : "无"}
                  </span>
                </div>
                <div className="role-impact-item">
                  <span className="role-impact-arrow">&#8594;</span>
                  <strong>失去页面：</strong>
                  <span className="role-impact-lose">
                    {impactInfo.isWebRole ? "非此角色的所有页面均不可见" : "Web 工作区页面不可见"}
                  </span>
                </div>
                <div className="role-impact-item">
                  <span className="role-impact-arrow">&#8594;</span>
                  <strong>可提交工序：</strong>
                  <span>{impactInfo.processes.length > 0 ? impactInfo.processes.join("、") : "无"}</span>
                </div>
                <div className="role-impact-item">
                  <span className="role-impact-arrow">&#8594;</span>
                  <strong>工厂范围：</strong>
                  <span>{impactInfo.factoryScope}</span>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
