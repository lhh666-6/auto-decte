import { useEffect, useState, useMemo } from "react";

import type { BambooEmployee, BambooPersonnelTransfer } from "./types";
import {
  DetailDrawer,
  DetailField,
} from "./shared/DetailDrawer";
import {
  ErrorAlert,
  PageHeader,
} from "./shared/SummaryCardGrid";
import { StatusBadge } from "./shared/StatusBadge";

interface FactoryInfo {
  factory_id: string;
  code: string;
  name: string;
}

/** Access extended fields that may be returned by the API but are not in the base type. */
function ext<T extends object>(obj: T, key: string): unknown {
  return (obj as Record<string, unknown>)[key];
}

function extStr<T extends object>(obj: T, key: string): string {
  return String(ext(obj, key) ?? "");
}

interface TeamNode {
  team_id: string;
  name: string;
  employeeCount: number;
  activeCount: number;
  inactiveCount: number;
}

interface TreeNode {
  factory: FactoryInfo;
  teams: TeamNode[];
}

type DetailTab = "overview" | "access" | "roles" | "transfers" | "activity";

export function AdminOrganizationPage() {
  const [factories, setFactories] = useState<FactoryInfo[]>([]);
  const [employees, setEmployees] = useState<BambooEmployee[]>([]);
  const [transfers, setTransfers] = useState<BambooPersonnelTransfer[]>([]);
  const [roles, setRoles] = useState<Array<{ role_code: string; display_name: string }>>([]);
  const [selectedFactoryId, setSelectedFactoryId] = useState("");
  const [selectedTeamId, setSelectedTeamId] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedEmployee, setSelectedEmployee] = useState<BambooEmployee | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    void loadInitial();
  }, []);

  async function loadInitial() {
    try {
      const [factResp, rolesResp] = await Promise.all([
        fetch("/api/v1/plant/factories", { credentials: "include" }),
        fetch("/api/v1/plant/roles", { credentials: "include" }),
      ]);
      if (factResp.ok) {
        const factData = (await factResp.json()) as { items: FactoryInfo[] };
        setFactories(factData.items ?? []);
      }
      if (rolesResp.ok) {
        const roleData = (await rolesResp.json()) as { items: Array<{ role_code: string; display_name: string }> };
        setRoles(roleData.items ?? []);
      }
    } catch {
      /* silent — optionally show warning */
    }
  }

  useEffect(() => {
    void loadEmployees();
  }, [selectedFactoryId]);

  async function loadEmployees() {
    setLoading(true);
    setError("");
    try {
      const fetchUrl = selectedFactoryId
        ? `/api/v1/plant/employees?factory_id=${encodeURIComponent(selectedFactoryId)}`
        : "/api/v1/plant/employees";

      const [empResult, transferResult] = await Promise.all([
        fetch(fetchUrl, { credentials: "include" }).then((r) => r.json()) as Promise<{ items: BambooEmployee[] }>,
        fetch("/api/v1/plant/personnel-transfers", { credentials: "include" }).then((r) => r.json()) as Promise<{ items: BambooPersonnelTransfer[] }>,
      ]);

      setEmployees(empResult.items ?? []);
      setTransfers(transferResult.items ?? []);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "数据加载失败");
    } finally {
      setLoading(false);
    }
  }

  /* ---- derived: tree nodes ---- */
  const factoryOptions = useMemo(() => {
    if (factories.length > 0) return factories;
    return [...new Map(employees.map((e) => [e.factory_id, { factory_id: e.factory_id, code: e.factory_id, name: e.factory_id }] as const)).values()];
  }, [factories, employees]);

  const treeNodes = useMemo((): TreeNode[] => {
    return factoryOptions.map((factory) => {
      const facEmployees = employees.filter((e) => e.factory_id === factory.factory_id);
      const teamMap = new Map<string, { active: number; inactive: number }>();
      for (const emp of facEmployees) {
        const team = (extStr(emp, "team_name") || emp.role_name) || "未分组";
        if (!teamMap.has(team)) teamMap.set(team, { active: 0, inactive: 0 });
        const entry = teamMap.get(team)!;
        const empStatus = extStr(emp, "status");
        if (empStatus === "INACTIVE" || empStatus === "SUSPENDED") {
          entry.inactive++;
        } else {
          entry.active++;
        }
      }
      const teams: TeamNode[] = Array.from(teamMap.entries()).map(([name, counts]) => ({
        team_id: `${factory.factory_id}:${name}`,
        name,
        employeeCount: counts.active + counts.inactive,
        activeCount: counts.active,
        inactiveCount: counts.inactive,
      }));
      return { factory, teams };
    });
  }, [factoryOptions, employees]);

  function filteredEmployees(): BambooEmployee[] {
    let list = employees;
    if (selectedFactoryId) {
      list = list.filter((e) => e.factory_id === selectedFactoryId);
    }
    if (selectedTeamId) {
      const [fid, teamName] = selectedTeamId.split(":");
      list = list.filter((e) => {
        const team = extStr(e, "team_name") || e.role_name || "未分组";
        return e.factory_id === fid && team === teamName;
      });
    }
    if (searchTerm.trim()) {
      const term = searchTerm.trim().toLowerCase();
      list = list.filter(
        (e) =>
          e.employee_name.toLowerCase().includes(term) ||
          e.employee_code.toLowerCase().includes(term) ||
          e.role_name.toLowerCase().includes(term),
      );
    }
    return list;
  }

  function employeeTransfers(employee: BambooEmployee) {
    return transfers.filter((t) => t.employee_code === employee.employee_code);
  }

  function isCrossFactory(t: BambooPersonnelTransfer): boolean {
    return t.source_factory_id !== t.target_factory_id;
  }

  /* ---- data-testid helpers ---- */
  function tid(suffix: string): string {
    return `admin-org-${suffix}`;
  }

  const displayEmployees = filteredEmployees();

  return (
    <section className="admin-org-page" data-testid={tid("page")}>
      <PageHeader
        title="组织架构"
        subtitle="查看各工厂员工档案、岗位角色和历史调动。"
      />

      {error && <ErrorAlert message={error} />}

      <div className="admin-org-layout" data-testid={tid("layout")}>
        {/* ===== LEFT: Organization Tree ===== */}
        <aside className="admin-org-tree" data-testid={tid("tree")}>
          <h2 className="admin-org-tree-title">组织树</h2>
          {loading && treeNodes.length === 0 ? (
            <div role="status" className="empty-state">加载中…</div>
          ) : treeNodes.length === 0 ? (
            <div className="empty-state">暂无工厂数据</div>
          ) : (
            <ul className="org-tree-list">
              {/* "All" node */}
              <li key="all" className="org-tree-item">
                <button
                  type="button"
                  className={selectedFactoryId === "" && selectedTeamId === "" ? "org-tree-node org-tree-node--active" : "org-tree-node"}
                  onClick={() => { setSelectedFactoryId(""); setSelectedTeamId(""); }}
                  aria-label="显示全部工厂和员工"
                  data-testid={tid("tree-all")}
                >
                  <span className="org-tree-label">全部工厂</span>
                  <span className="org-tree-count">{employees.length}</span>
                </button>
              </li>

              {treeNodes.map((node) => (
                <li key={node.factory.factory_id} className="org-tree-item">
                  {/* Factory node */}
                  <button
                    type="button"
                    className={selectedFactoryId === node.factory.factory_id && selectedTeamId === "" ? "org-tree-node org-tree-node--active" : "org-tree-node"}
                    onClick={() => { setSelectedFactoryId(node.factory.factory_id); setSelectedTeamId(""); }}
                    aria-label={`工厂 ${node.factory.name}，${node.factory.code}`}
                    data-testid={tid(`tree-factory-${node.factory.factory_id}`)}
                  >
                    <span className="org-tree-icon" aria-hidden="true">🏭</span>
                    <span className="org-tree-label">{node.factory.name}</span>
                    <span className="org-tree-count">{node.teams.reduce((s, t) => s + t.employeeCount, 0)}</span>
                  </button>

                  {/* Team nodes */}
                  {node.teams.length > 0 && (
                    <ul className="org-tree-sublist">
                      {node.teams.map((team) => (
                        <li key={team.team_id} className="org-tree-subitem">
                          <button
                            type="button"
                            className={selectedTeamId === team.team_id ? "org-tree-node org-tree-node--active org-tree-node--child" : "org-tree-node org-tree-node--child"}
                            onClick={() => { setSelectedFactoryId(node.factory.factory_id); setSelectedTeamId(team.team_id); }}
                            aria-label={`班组 ${team.name}，${team.employeeCount} 人`}
                            data-testid={tid(`tree-team-${team.team_id}`)}
                          >
                            <span className="org-tree-icon" aria-hidden="true">👥</span>
                            <span className="org-tree-label">{team.name}</span>
                            <span className="org-tree-count">{team.employeeCount}</span>
                            {team.inactiveCount > 0 && (
                              <span className="org-tree-inactive-badge" title={`${team.inactiveCount} 人已停用`} aria-label={`${team.inactiveCount} 人已停用`}>
                                停{team.inactiveCount}
                              </span>
                            )}
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          )}
        </aside>

        {/* ===== MIDDLE: Employee Table ===== */}
        <main className="admin-org-employees" data-testid={tid("employees")}>
          <div className="admin-org-search">
            <label htmlFor="org-employee-search" className="visually-hidden">搜索员工</label>
            <input
              id="org-employee-search"
              type="search"
              placeholder="搜索姓名、工号、岗位…"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              aria-label="搜索员工"
              data-testid={tid("search")}
            />
          </div>

          {loading ? (
            <div role="status" className="empty-state" data-testid={tid("loading")}>加载员工数据中…</div>
          ) : displayEmployees.length === 0 ? (
            <div className="empty-state" data-testid={tid("empty")}>
              {searchTerm ? "无匹配员工" : "当前没有员工数据"}
            </div>
          ) : (
            <div className="governed-table-wrap" data-testid={tid("table")}>
              <table className="governed-table">
                <thead>
                  <tr>
                    <th>工号</th>
                    <th>姓名</th>
                    <th>班组</th>
                    <th>岗位</th>
                    <th>Web 角色</th>
                    <th>Bamboo 角色</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {displayEmployees.map((emp) => (
                    <tr
                      key={emp.employee_code}
                      className="governed-table-row-clickable"
                      onClick={() => { setSelectedEmployee(emp); setDetailTab("overview"); }}
                      data-testid={tid(`row-${emp.employee_code}`)}
                    >
                      <td>{emp.employee_code}</td>
                      <td>{emp.employee_name}</td>
                      <td>{extStr(emp, "team_name") || emp.role_name}</td>
                      <td>{emp.role_name}</td>
                      <td>{extStr(emp, "web_role") || "—"}</td>
                      <td>{emp.role_code}</td>
                      <td>
                        <StatusBadge status={(extStr(emp, "status") === "INACTIVE" || extStr(emp, "status") === "SUSPENDED") ? "INACTIVE" : "ACTIVE"} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {/* ===== RIGHT: Detail Drawer ===== */}
      <DetailDrawer
        open={selectedEmployee !== null}
        onClose={() => setSelectedEmployee(null)}
        title={selectedEmployee ? `${selectedEmployee.employee_name} 的档案` : ""}
        data-testid={tid("detail-drawer")}
      >
        {selectedEmployee && (
          <div className="detail-drawer-fields">
            {/* In-drawer tabs */}
            <nav className="finance-drawer-tabs" aria-label="详情分类">
              {([
                ["overview", "概览"],
                ["access", "访问范围"],
                ["roles", "角色"],
                ["transfers", "调动"],
                ["activity", "活动"],
              ] as const).map(([tab, label]) => (
                <button
                  key={tab}
                  type="button"
                  className={`finance-drawer-tab ${detailTab === tab ? "finance-drawer-tab--active" : ""}`}
                  onClick={() => setDetailTab(tab)}
                  data-testid={tid(`detail-tab-${tab}`)}
                >
                  {label}
                </button>
              ))}
            </nav>

            <div className="finance-detail-section" style={{ marginTop: 12 }}>
              {detailTab === "overview" && (
                <>
                  <DetailField label="姓名" value={selectedEmployee.employee_name} />
                  <DetailField label="工号" value={selectedEmployee.employee_code} />
                  <DetailField label="工厂" value={selectedEmployee.factory_id} />
                  <DetailField label="当前岗位" value={selectedEmployee.role_name} />
                  <DetailField label="岗位编号" value={selectedEmployee.role_code} />
                  <DetailField label="班组" value={extStr(selectedEmployee, "team_name") || "—"} />
                  <DetailField label="状态" value={(extStr(selectedEmployee, "status") === "INACTIVE" || extStr(selectedEmployee, "status") === "SUSPENDED") ? "已停用" : "正式有效"} />
                  <DetailField label="最近登录" value={extStr(selectedEmployee, "last_login_at") || "—"} />
                </>
              )}

              {detailTab === "access" && (
                <>
                  <h3>可访问工作区</h3>
                  <p>{extStr(selectedEmployee, "accessible_workspaces") || "—"}</p>
                </>
              )}

              {detailTab === "roles" && (
                <>
                  <h3>Web 角色</h3>
                  <p>{extStr(selectedEmployee, "web_role") || "无"}</p>
                  <h3>Bamboo 生产角色</h3>
                  <p>{selectedEmployee.role_name} ({selectedEmployee.role_code})</p>
                  {roles.length > 0 && (
                    <>
                      <h3>可分配角色</h3>
                      <div className="admin-org-role-list">
                        {roles.map((r) => (
                          <span key={r.role_code} className="org-role-chip" data-testid={tid(`role-chip-${r.role_code}`)}>
                            {r.display_name} ({r.role_code})
                          </span>
                        ))}
                      </div>
                    </>
                  )}
                </>
              )}

              {detailTab === "transfers" && (
                <>
                  {employeeTransfers(selectedEmployee).length > 0 && (
                    <>
                      <h3>历史调动</h3>
                      {employeeTransfers(selectedEmployee).map((t) => (
                        <div key={t.transfer_id} className="transfer-card" data-testid={tid(`transfer-${t.transfer_id}`)}>
                          {isCrossFactory(t) && (
                            <span className="transfer-cross-badge" aria-label="跨厂调动">跨厂调动</span>
                          )}
                          <DetailField label="原岗位" value={t.from_role} />
                          <DetailField label="目标岗位" value={t.to_role} />
                          <DetailField label="原工厂" value={t.source_factory_id} />
                          <DetailField label="目标工厂" value={t.target_factory_id} />
                          <DetailField label="发起日期" value={extStr(t, "initiated_at") || "—"} />
                          <DetailField label="审批日期" value={extStr(t, "approved_at") || "—"} />
                          <DetailField label="执行日期" value={extStr(t, "executed_at") || "—"} />
                          <DetailField label="状态" value={t.status} />
                          <DetailField label="原因" value={t.reason} />
                        </div>
                      ))}
                    </>
                  )}
                  {employeeTransfers(selectedEmployee).length === 0 && (
                    <p className="empty-state">暂无调动记录</p>
                  )}
                </>
              )}

              {detailTab === "activity" && (
                <>
                  <h3>最近登录</h3>
                  <p>{extStr(selectedEmployee, "last_login_at") || "—"}</p>
                  <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
                    <button
                      type="button"
                      className="org-action-btn org-action-suspend"
                      onClick={() => { /* suspend API call */ }}
                      data-testid={tid("detail-suspend")}
                    >
                      {(extStr(selectedEmployee, "status") === "INACTIVE" || extStr(selectedEmployee, "status") === "SUSPENDED") ? "恢复员工" : "停用员工"}
                    </button>
                  </div>
                </>
              )}
            </div>
          </div>
        )}
      </DetailDrawer>
    </section>
  );
}
