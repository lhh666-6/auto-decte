import { useEffect, useState, useMemo } from "react";

import type { BambooEmployee, BambooPersonnelTransfer } from "./types";
import {
  DetailDrawer,
  DetailField,
} from "./shared/DetailDrawer";
import {
  ErrorAlert,
  PageHeader,
  SummaryCardGrid,
} from "./shared/SummaryCardGrid";
import type { SummaryCard } from "./shared/SummaryCardGrid";
import { StatusBadge } from "./shared/StatusBadge";
import { FilterToolbar } from "./shared/FilterToolbar";
import type { FilterOption, AppliedFilter } from "./shared/FilterToolbar";

// ── Types ────────────────────────────────────────────────────────

interface FactoryInfo {
  factory_id: string;
  code: string;
  name: string;
}

type CreateStep = "identity" | "account" | "confirm";

type DetailTab = "overview" | "permissions" | "account" | "transfers" | "access";

// ── Helpers ──────────────────────────────────────────────────────

/** Access extended fields that may be returned by the API but are not in the base type. */
function ext<T extends object>(obj: T, key: string): unknown {
  return (obj as Record<string, unknown>)[key];
}

function extStr<T extends object>(obj: T, key: string): string {
  return String(ext(obj, key) ?? "");
}

// ── Chinese label mappings ───────────────────────────────────────

/** role_code → Chinese job label (fallback, overridden by API data when available). */
const ROLE_CODE_TO_LABEL_FALLBACK: Record<string, string> = {
  SORT_OPERATOR: "分选工",
  DIPPING_OPERATOR: "浸胶工",
  DRYING_RACK_OPERATOR: "干燥工",
  INSPECTOR: "检测人",
  SUPERVISOR: "主管",
  PLANT_MANAGER: "厂长",
  FINANCE_APPROVER: "财务审批",
  SYSTEM_ADMIN: "系统管理员",
};

/** role_code → display group for the org tree. */
function roleToJobGroup(roleCode: string): string {
  const map: Record<string, string> = {
    SORT_OPERATOR: "分选",
    DIPPING_OPERATOR: "浸胶",
    DRYING_RACK_OPERATOR: "干燥",
    INSPECTOR: "检测",
    SUPERVISOR: "管理",
    PLANT_MANAGER: "管理",
    FINANCE_APPROVER: "管理",
    SYSTEM_ADMIN: "管理",
  };
  return map[roleCode] ?? "其他";
}

/** Ordered job groups for the org tree. */
const JOB_GROUP_ORDER = ["分选", "浸胶", "干燥", "检测", "管理", "其他"];

/** Web role display names. */
const WEB_ROLE_LABELS: Record<string, string> = {
  ADMIN: "系统管理员",
  FINANCE: "财务审批",
  PLANT_MANAGER: "厂长",
};

// ── Component ────────────────────────────────────────────────────

export function AdminOrganizationPage() {
  const [factories, setFactories] = useState<FactoryInfo[]>([]);
  const [employees, setEmployees] = useState<BambooEmployee[]>([]);
  const [transfers, setTransfers] = useState<BambooPersonnelTransfer[]>([]);
  const [roles, setRoles] = useState<Array<{ role_code: string; display_name: string }>>([]);
  const [selectedFactoryId, setSelectedFactoryId] = useState("");
  const [selectedJobGroup, setSelectedJobGroup] = useState("");
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedEmployee, setSelectedEmployee] = useState<BambooEmployee | null>(null);
  const [detailTab, setDetailTab] = useState<DetailTab>("overview");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [initError, setInitError] = useState("");

  // Filters
  const [filterFactory, setFilterFactory] = useState("");
  const [filterJob, setFilterJob] = useState("");
  const [filterStatus, setFilterStatus] = useState("");

  useEffect(() => {
    setLoading(true);
    setError("");
    setInitError("");
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
      } else {
        throw new Error(`工厂列表加载失败 (${factResp.status})`);
      }
      if (rolesResp.ok) {
        const roleData = (await rolesResp.json()) as { items: Array<{ role_code: string; display_name: string }> };
        setRoles(roleData.items ?? []);
      }
    } catch (cause: unknown) {
      setInitError(cause instanceof Error ? cause.message : "基础数据加载失败");
    }
  }

  // ── New Employee wizard state ──
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createStep, setCreateStep] = useState<CreateStep>("identity");
  const [createEmpCode, setCreateEmpCode] = useState("");
  const [createEmpName, setCreateEmpName] = useState("");
  const [createEmpFactory, setCreateEmpFactory] = useState("");
  const [createEmpJob, setCreateEmpJob] = useState("");
  const [createEmpPin, setCreateEmpPin] = useState("");
  const [createEmpActive, setCreateEmpActive] = useState(true);
  const [createEmpSubmitting, setCreateEmpSubmitting] = useState(false);
  const [createEmpError, setCreateEmpError] = useState("");
  const [createEmpSuccess, setCreateEmpSuccess] = useState("");
  const [jobPresets, setJobPresets] = useState<Array<{ label: string; bamboo_role: string; web_roles: string[] }>>([]);
  const [adminFactories, setAdminFactories] = useState<FactoryInfo[]>([]);

  async function openCreateForm() {
    setCreateEmpError("");
    setCreateEmpSuccess("");
    setCreateEmpCode("");
    setCreateEmpName("");
    setCreateEmpFactory("");
    setCreateEmpJob("");
    setCreateEmpPin("");
    setCreateEmpActive(true);
    setCreateStep("identity");
    setShowCreateForm(true);
    try {
      const [fResp, jResp] = await Promise.all([
        fetch("/api/v1/admin/factories", { credentials: "include" }),
        fetch("/api/v1/admin/job-presets", { credentials: "include" }),
      ]);
      if (fResp.ok) {
        const data = (await fResp.json()) as { items: FactoryInfo[] };
        setAdminFactories(data.items ?? []);
      }
      if (jResp.ok) {
        const data = (await jResp.json()) as { items: Array<{ label: string; bamboo_role: string; web_roles: string[] }> };
        setJobPresets(data.items ?? []);
      }
    } catch { /* modal stays open; dropdowns may be empty */ }
  }

  async function submitCreateEmployee() {
    if (!createEmpCode.trim()) { setCreateEmpError("请输入工号"); return; }
    if (!createEmpName.trim()) { setCreateEmpError("请输入姓名"); return; }
    if (!createEmpFactory) { setCreateEmpError("请选择所属工厂"); return; }
    if (!createEmpJob) { setCreateEmpError("请选择岗位"); return; }
    if (!createEmpPin || createEmpPin.length < 4) { setCreateEmpError("PIN 至少 4 位数字"); return; }

    const job = jobPresets.find((j) => j.label === createEmpJob);
    if (!job) { setCreateEmpError("所选岗位无效"); return; }

    setCreateEmpSubmitting(true);
    setCreateEmpError("");
    try {
      const resp = await fetch("/api/v1/admin/employees", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": getCsrfToken(),
        },
        body: JSON.stringify({
          employee_code: createEmpCode.trim(),
          employee_name: createEmpName.trim(),
          factory_id: createEmpFactory,
          bamboo_role: job.bamboo_role,
          web_roles: job.web_roles,
          initial_pin: createEmpPin,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({})) as { detail?: { detail?: string } };
        throw new Error(err.detail?.detail ?? `创建失败 (${resp.status})`);
      }
      const result = await resp.json() as { employee_code: string };
      setCreateEmpSuccess(`员工 ${result.employee_code} 创建成功`);
      setCreateEmpError("");
      await loadEmployees();
      setTimeout(() => { setShowCreateForm(false); setCreateEmpSuccess(""); }, 2000);
    } catch (cause: unknown) {
      setCreateEmpError(cause instanceof Error ? cause.message : "创建失败");
    } finally {
      setCreateEmpSubmitting(false);
    }
  }

  /* ---- CSRF token helper ---- */
  function getCsrfToken(): string {
    const meta = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]');
    return meta?.content ?? "";
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

  // ── Derived data ───────────────────────────────────────────────

  const factoryNameMap = useMemo((): Record<string, string> => {
    const map: Record<string, string> = {};
    for (const f of factories) {
      map[f.factory_id] = f.name || f.code || f.factory_id;
    }
    // Fill gaps from employees
    for (const e of employees) {
      if (!map[e.factory_id]) map[e.factory_id] = e.factory_id;
    }
    return map;
  }, [factories, employees]);

  const jobLabelMap = useMemo((): Record<string, string> => {
    const map: Record<string, string> = { ...ROLE_CODE_TO_LABEL_FALLBACK };
    // Enrich from job presets if available
    for (const jp of jobPresets) {
      map[jp.bamboo_role] = jp.label;
    }
    return map;
  }, [jobPresets]);

  function getFactoryName(factoryId: string): string {
    return factoryNameMap[factoryId] ?? factoryId;
  }

  function getJobLabel(roleCode: string): string {
    return jobLabelMap[roleCode] ?? roleCode;
  }

  const factoryOptions = useMemo(() => {
    if (factories.length > 0) return factories;
    return [...new Map(employees.map((e) => [e.factory_id, { factory_id: e.factory_id, code: e.factory_id, name: e.factory_id }] as const)).values()];
  }, [factories, employees]);

  // ── Summary cards ──────────────────────────────────────────────

  const summaryCards = useMemo((): SummaryCard[] => {
    const total = employees.length;
    const active = employees.filter((e) => {
      const s = extStr(e, "status");
      return s !== "INACTIVE" && s !== "SUSPENDED";
    }).length;
    const inactive = total - active;

    const cards: SummaryCard[] = [
      { key: "total", label: "员工总数", value: total },
      { key: "active", label: "在职人数", value: active },
      { key: "inactive", label: "停用人数", value: inactive },
    ];

    // Per-factory counts
    for (const f of factoryOptions) {
      const count = employees.filter((e) => e.factory_id === f.factory_id).length;
      if (count > 0) {
        cards.push({
          key: `factory-${f.factory_id}`,
          label: getFactoryName(f.factory_id),
          value: count,
        });
      }
    }

    return cards;
  }, [employees, factoryOptions, factoryNameMap]);

  // ── Org tree: factory → job group ──────────────────────────────

  interface JobGroupNode {
    groupKey: string;
    groupLabel: string;
    employeeCount: number;
    activeCount: number;
    inactiveCount: number;
  }

  interface TreeNode {
    factory: FactoryInfo;
    jobGroups: JobGroupNode[];
  }

  const treeNodes = useMemo((): TreeNode[] => {
    return factoryOptions.map((factory) => {
      const facEmployees = employees.filter((e) => e.factory_id === factory.factory_id);
      const groupMap = new Map<string, { active: number; inactive: number }>();
      for (const emp of facEmployees) {
        const group = roleToJobGroup(emp.role_code);
        if (!groupMap.has(group)) groupMap.set(group, { active: 0, inactive: 0 });
        const entry = groupMap.get(group)!;
        const empStatus = extStr(emp, "status");
        if (empStatus === "INACTIVE" || empStatus === "SUSPENDED") {
          entry.inactive++;
        } else {
          entry.active++;
        }
      }
      const jobGroups: JobGroupNode[] = JOB_GROUP_ORDER
        .filter((g) => groupMap.has(g))
        .map((g) => {
          const counts = groupMap.get(g)!;
          return {
            groupKey: `${factory.factory_id}:${g}`,
            groupLabel: g,
            employeeCount: counts.active + counts.inactive,
            activeCount: counts.active,
            inactiveCount: counts.inactive,
          };
        });
      return { factory, jobGroups };
    });
  }, [factoryOptions, employees]);

  // ── Employee filtering ─────────────────────────────────────────

  function filteredEmployees(): BambooEmployee[] {
    let list = employees;
    if (selectedFactoryId) {
      list = list.filter((e) => e.factory_id === selectedFactoryId);
    }
    if (selectedJobGroup) {
      list = list.filter((e) => roleToJobGroup(e.role_code) === selectedJobGroup);
    }
    // Toolbar filters (in addition to tree selection)
    if (filterFactory) {
      list = list.filter((e) => e.factory_id === filterFactory);
    }
    if (filterJob) {
      list = list.filter((e) => e.role_code === filterJob);
    }
    if (filterStatus) {
      list = list.filter((e) => {
        const s = extStr(e, "status");
        if (filterStatus === "ACTIVE") return s !== "INACTIVE" && s !== "SUSPENDED";
        if (filterStatus === "INACTIVE") return s === "INACTIVE" || s === "SUSPENDED";
        return true;
      });
    }
    if (searchTerm.trim()) {
      const term = searchTerm.trim().toLowerCase();
      list = list.filter(
        (e) =>
          e.employee_name.toLowerCase().includes(term) ||
          e.employee_code.toLowerCase().includes(term) ||
          e.role_name.toLowerCase().includes(term) ||
          getJobLabel(e.role_code).toLowerCase().includes(term),
      );
    }
    return list;
  }

  // ── Filter definitions ─────────────────────────────────────────

  const filterDefs = useMemo((): FilterOption[] => {
    const factoryOpts = factoryOptions.map((f) => ({ value: f.factory_id, label: getFactoryName(f.factory_id) }));
    const uniqueRoleCodes = [...new Set(employees.map((e) => e.role_code))];
    const jobOpts = uniqueRoleCodes.map((rc) => ({ value: rc, label: getJobLabel(rc) }));
    return [
      {
        key: "factory",
        label: "工厂",
        options: [{ value: "", label: "全部工厂" }, ...factoryOpts],
      },
      {
        key: "job",
        label: "岗位",
        options: [{ value: "", label: "全部岗位" }, ...jobOpts],
      },
      {
        key: "status",
        label: "状态",
        options: [
          { value: "", label: "全部状态" },
          { value: "ACTIVE", label: "正式有效" },
          { value: "INACTIVE", label: "已停用" },
        ],
      },
    ];
  }, [factoryOptions, employees, factoryNameMap, jobLabelMap]);

  const appliedFilters = useMemo((): AppliedFilter[] => {
    const result: AppliedFilter[] = [];
    if (filterFactory) result.push({ key: "factory", value: filterFactory });
    if (filterJob) result.push({ key: "job", value: filterJob });
    if (filterStatus) result.push({ key: "status", value: filterStatus });
    return result;
  }, [filterFactory, filterJob, filterStatus]);

  function handleFilterChange(applied: AppliedFilter[]) {
    const factoryF = applied.find((f) => f.key === "factory")?.value ?? "";
    const jobF = applied.find((f) => f.key === "job")?.value ?? "";
    const statusF = applied.find((f) => f.key === "status")?.value ?? "";
    setFilterFactory(factoryF);
    setFilterJob(jobF);
    setFilterStatus(statusF);
  }

  // ── Detail helpers ─────────────────────────────────────────────

  function employeeTransfers(employee: BambooEmployee) {
    return transfers.filter((t) => t.employee_code === employee.employee_code);
  }

  function isCrossFactory(t: BambooPersonnelTransfer): boolean {
    return t.source_factory_id !== t.target_factory_id;
  }

  // ── Wizard step helpers ────────────────────────────────────────

  function canAdvanceFromIdentity(): boolean {
    return createEmpCode.trim() !== "" && createEmpName.trim() !== "" && createEmpFactory !== "" && createEmpJob !== "";
  }

  function canAdvanceFromAccount(): boolean {
    return createEmpPin.length >= 4;
  }

  function selectedJobPreset() {
    return jobPresets.find((j) => j.label === createEmpJob);
  }

  // ── data-testid helper ─────────────────────────────────────────

  function tid(suffix: string): string {
    return `admin-org-${suffix}`;
  }

  const displayEmployees = filteredEmployees();

  // ── Render ─────────────────────────────────────────────────────

  return (
    <section className="admin-org-page" data-testid={tid("page")}>
      <PageHeader
        title="组织架构"
        subtitle="查看各工厂员工档案、岗位角色和历史调动。"
      />

      {initError && <ErrorAlert message={initError} />}
      {error && <ErrorAlert message={error} />}

      {/* ── Summary Cards ── */}
      <SummaryCardGrid cards={summaryCards} />

      {/* ── Toolbar: New Employee ── */}
      <div className="admin-org-toolbar" style={{ display: "flex", justifyContent: "flex-end", marginBottom: 0 }}>
        <button
          type="button"
          className="btn primary"
          onClick={() => void openCreateForm()}
          data-testid={tid("btn-create-employee")}
        >
          + 新增员工
        </button>
      </div>

      <div className="admin-org-layout" data-testid={tid("layout")}>
        {/* ===== LEFT: Organization Tree (Factory → Job Groups) ===== */}
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
                  className={selectedFactoryId === "" && selectedJobGroup === "" ? "org-tree-node org-tree-node--active" : "org-tree-node"}
                  onClick={() => { setSelectedFactoryId(""); setSelectedJobGroup(""); }}
                  aria-label="显示全部工厂和员工"
                  data-testid={tid("tree-all")}
                >
                  <span className="org-tree-label">全部员工</span>
                  <span className="org-tree-count">{employees.length}</span>
                </button>
              </li>

              {treeNodes.map((node) => (
                <li key={node.factory.factory_id} className="org-tree-item">
                  {/* Factory node */}
                  <button
                    type="button"
                    className={selectedFactoryId === node.factory.factory_id && selectedJobGroup === "" ? "org-tree-node org-tree-node--active" : "org-tree-node"}
                    onClick={() => { setSelectedFactoryId(node.factory.factory_id); setSelectedJobGroup(""); }}
                    aria-label={`工厂 ${node.factory.name}，${node.factory.code}`}
                    data-testid={tid(`tree-factory-${node.factory.factory_id}`)}
                  >
                    <span className="org-tree-icon" aria-hidden="true">🏭</span>
                    <span className="org-tree-label">{node.factory.name || node.factory.factory_id}</span>
                    <span className="org-tree-count">{node.jobGroups.reduce((s, g) => s + g.employeeCount, 0)}</span>
                  </button>

                  {/* Job group nodes */}
                  {node.jobGroups.length > 0 && (
                    <ul className="org-tree-sublist">
                      {node.jobGroups.map((group) => (
                        <li key={group.groupKey} className="org-tree-subitem">
                          <button
                            type="button"
                            className={selectedJobGroup === group.groupLabel && selectedFactoryId === node.factory.factory_id ? "org-tree-node org-tree-node--active org-tree-node--child" : "org-tree-node org-tree-node--child"}
                            onClick={() => { setSelectedFactoryId(node.factory.factory_id); setSelectedJobGroup(group.groupLabel); }}
                            aria-label={`${group.groupLabel}，${group.employeeCount} 人`}
                            data-testid={tid(`tree-group-${group.groupKey}`)}
                          >
                            <span className="org-tree-icon" aria-hidden="true">👥</span>
                            <span className="org-tree-label">{group.groupLabel}</span>
                            <span className="org-tree-count">{group.employeeCount}</span>
                            {group.inactiveCount > 0 && (
                              <span className="org-tree-inactive-badge" title={`${group.inactiveCount} 人已停用`} aria-label={`${group.inactiveCount} 人已停用`}>
                                停{group.inactiveCount}
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

        {/* ===== RIGHT: Employee Table ===== */}
        <main className="admin-org-employees" data-testid={tid("employees")}>
          {/* Search + Filter bar */}
          <div className="admin-org-toolbar-row">
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
            <div className="admin-org-filter-bar">
              <FilterToolbar
                filters={filterDefs}
                applied={appliedFilters}
                onChange={handleFilterChange}
              />
            </div>
          </div>

          {loading ? (
            <div role="status" className="empty-state" data-testid={tid("loading")}>加载员工数据中…</div>
          ) : displayEmployees.length === 0 ? (
            <div className="empty-state" data-testid={tid("empty")}>
              {searchTerm || filterFactory || filterJob || filterStatus ? "无匹配员工" : "当前没有员工数据"}
            </div>
          ) : (
            <div className="governed-table-wrap" data-testid={tid("table")}>
              <table className="governed-table">
                <thead>
                  <tr>
                    <th>工号</th>
                    <th>姓名</th>
                    <th>所属工厂</th>
                    <th>岗位</th>
                    <th>账号状态</th>
                    <th>最近登录</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {displayEmployees.map((emp) => {
                    const empStatus = extStr(emp, "status");
                    const lastLogin = extStr(emp, "last_login_at");
                    const isInactive = empStatus === "INACTIVE" || empStatus === "SUSPENDED";
                    return (
                      <tr
                        key={emp.employee_code}
                        className="governed-table-row-clickable"
                        onClick={() => { setSelectedEmployee(emp); setDetailTab("overview"); }}
                        data-testid={tid(`row-${emp.employee_code}`)}
                      >
                        <td>{emp.employee_code}</td>
                        <td>{emp.employee_name}</td>
                        <td>{getFactoryName(emp.factory_id)}</td>
                        <td>{getJobLabel(emp.role_code)}</td>
                        <td>
                          <StatusBadge status={isInactive ? "INACTIVE" : "ACTIVE"} />
                        </td>
                        <td className="admin-org-cell-muted">
                          {lastLogin ? formatLastLogin(lastLogin) : "—"}
                        </td>
                        <td>
                          <button
                            type="button"
                            className="org-action-link"
                            onClick={(e) => { e.stopPropagation(); setSelectedEmployee(emp); setDetailTab("overview"); }}
                          >
                            查看
                          </button>
                        </td>
                      </tr>
                    );
                  })}
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
                ["permissions", "权限与岗位"],
                ["account", "账号"],
                ["transfers", "调动"],
                ["access", "访问范围"],
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
                  <DetailField label="工厂" value={getFactoryName(selectedEmployee.factory_id)} />
                  <DetailField label="当前岗位" value={getJobLabel(selectedEmployee.role_code)} />
                  <DetailField label="岗位编号" value={selectedEmployee.role_code} />
                  <DetailField label="班组" value={extStr(selectedEmployee, "team_name") || "—"} />
                  <DetailField label="状态" value={(extStr(selectedEmployee, "status") === "INACTIVE" || extStr(selectedEmployee, "status") === "SUSPENDED") ? "已停用" : "正式有效"} />
                  <DetailField label="最近登录" value={formatLastLogin(extStr(selectedEmployee, "last_login_at"))} />
                </>
              )}

              {detailTab === "permissions" && (
                <>
                  {/* Business view */}
                  <h3 className="detail-section-title">业务视图</h3>
                  <DetailField label="生产岗位" value={getJobLabel(selectedEmployee.role_code)} />
                  <DetailField label="移动端可用性" value={(extStr(selectedEmployee, "status") === "INACTIVE" || extStr(selectedEmployee, "status") === "SUSPENDED") ? "已停用" : "可用"} />
                  <DetailField
                    label="Web 角色"
                    value={
                      extStr(selectedEmployee, "web_role")
                        ? WEB_ROLE_LABELS[extStr(selectedEmployee, "web_role")] ?? extStr(selectedEmployee, "web_role")
                        : "无"
                    }
                  />
                  <DetailField label="允许记录工序" value={selectedEmployee.role_code ? "是" : "—"} />

                  {/* Technical details fold */}
                  <details className="admin-org-tech-fold" style={{ marginTop: 16 }}>
                    <summary className="admin-org-tech-fold-summary">技术详情</summary>
                    <div style={{ marginTop: 8, padding: "0 8px" }}>
                      <DetailField label="Bamboo Role" value={selectedEmployee.role_code} />
                      <DetailField label="Allowed Stage" value={extStr(selectedEmployee, "allowed_stage") || "—"} />
                      <DetailField label="Factory ID" value={selectedEmployee.factory_id} />
                      <DetailField label="Role Code" value={selectedEmployee.role_code} />
                    </div>
                  </details>

                  {/* Available roles */}
                  {roles.length > 0 && (
                    <div style={{ marginTop: 16 }}>
                      <h3 className="detail-section-title">可分配角色</h3>
                      <div className="admin-org-role-list">
                        {roles.map((r) => (
                          <span key={r.role_code} className="org-role-chip" data-testid={tid(`role-chip-${r.role_code}`)}>
                            {r.display_name} ({r.role_code})
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}

              {detailTab === "account" && (
                <>
                  <DetailField label="工号" value={selectedEmployee.employee_code} />
                  <DetailField label="姓名" value={selectedEmployee.employee_name} />
                  <DetailField label="账号状态" value={(extStr(selectedEmployee, "status") === "INACTIVE" || extStr(selectedEmployee, "status") === "SUSPENDED") ? "已停用" : "正式有效"} />
                  <DetailField label="最近登录" value={formatLastLogin(extStr(selectedEmployee, "last_login_at"))} />

                  <div style={{ marginTop: 16, display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button
                      type="button"
                      className="org-action-btn org-action-suspend"
                      disabled
                      title="员工状态调整暂未开放"
                      data-testid={tid("detail-suspend")}
                    >
                      {(extStr(selectedEmployee, "status") === "INACTIVE" || extStr(selectedEmployee, "status") === "SUSPENDED") ? "恢复员工（暂未开放）" : "停用员工（暂未开放）"}
                    </button>
                    <button
                      type="button"
                      className="org-action-btn org-action-reset-pin"
                      disabled
                      title="PIN 重置功能暂未开放"
                      data-testid={tid("detail-reset-pin")}
                    >
                      重置 PIN（暂未开放）
                    </button>
                  </div>
                </>
              )}

              {detailTab === "transfers" && (
                <>
                  {employeeTransfers(selectedEmployee).length > 0 && (
                    <>
                      <h3 className="detail-section-title">历史调动</h3>
                      {employeeTransfers(selectedEmployee).map((t) => (
                        <div key={t.transfer_id} className="transfer-card" data-testid={tid(`transfer-${t.transfer_id}`)}>
                          {isCrossFactory(t) && (
                            <span className="transfer-cross-badge" aria-label="跨厂调动">跨厂调动</span>
                          )}
                          <DetailField label="原岗位" value={t.from_role} />
                          <DetailField label="目标岗位" value={t.to_role} />
                          <DetailField label="原工厂" value={getFactoryName(t.source_factory_id)} />
                          <DetailField label="目标工厂" value={getFactoryName(t.target_factory_id)} />
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

              {detailTab === "access" && (
                <>
                  <h3 className="detail-section-title">可访问工作区</h3>
                  <p>{extStr(selectedEmployee, "accessible_workspaces") || "—"}</p>
                </>
              )}
            </div>
          </div>
        )}
      </DetailDrawer>

      {/* ── Create Employee Two-Step Wizard ── */}
      {showCreateForm && (
        <div className="modal-backdrop" role="presentation" onClick={() => !createEmpSubmitting && setShowCreateForm(false)}>
          <div
            className="modal-panel admin-create-wizard"
            role="dialog"
            aria-modal="true"
            aria-labelledby="createEmpTitle"
            onClick={(e) => e.stopPropagation()}
            data-testid={tid("dialog-create-employee")}
          >
            <header>
              <h3 id="createEmpTitle">新增员工</h3>
              <button type="button" disabled={createEmpSubmitting} onClick={() => setShowCreateForm(false)} aria-label="关闭">×</button>
            </header>

            {/* Wizard step indicator */}
            <div className="wizard-steps" aria-label="创建步骤">
              {(["identity", "account", "confirm"] as CreateStep[]).map((step, idx) => {
                const labels = ["身份", "账号", "确认"];
                const stepNum = idx + 1;
                const isActive = createStep === step;
                const isDone = (createStep === "account" && idx === 0) || (createStep === "confirm" && idx < 2);
                return (
                  <div key={step} className={`wizard-step ${isActive ? "wizard-step--active" : ""} ${isDone ? "wizard-step--done" : ""}`}>
                    <span className="wizard-step-num">{isDone ? "✓" : stepNum}</span>
                    <span className="wizard-step-label">{labels[idx]}</span>
                  </div>
                );
              })}
            </div>

            <div className="modal-body">
              {createEmpSuccess && (
                <div className="banner success" role="status">{createEmpSuccess}</div>
              )}
              {createEmpError && (
                <div className="banner danger" role="alert">{createEmpError}</div>
              )}

              {/* Step 1: Identity */}
              {createStep === "identity" && (
                <div className="wizard-step-body">
                  <label>
                    工号 *
                    <input
                      type="text"
                      value={createEmpCode}
                      onChange={(e) => setCreateEmpCode(e.target.value)}
                      placeholder="例如 SORT002"
                      disabled={createEmpSubmitting}
                      data-testid={tid("create-emp-code")}
                    />
                  </label>

                  <label>
                    姓名 *
                    <input
                      type="text"
                      value={createEmpName}
                      onChange={(e) => setCreateEmpName(e.target.value)}
                      placeholder="例如 王小明"
                      disabled={createEmpSubmitting}
                      data-testid={tid("create-emp-name")}
                    />
                  </label>

                  <label>
                    所属工厂 *
                    <select
                      value={createEmpFactory}
                      onChange={(e) => setCreateEmpFactory(e.target.value)}
                      disabled={createEmpSubmitting}
                      data-testid={tid("create-emp-factory")}
                    >
                      <option value="">-- 选择工厂 --</option>
                      {(adminFactories.length > 0 ? adminFactories : factories).map((f) => (
                        <option key={f.factory_id} value={f.factory_id}>{f.name || f.code || f.factory_id}</option>
                      ))}
                    </select>
                  </label>

                  <label>
                    岗位 *
                    <select
                      value={createEmpJob}
                      onChange={(e) => setCreateEmpJob(e.target.value)}
                      disabled={createEmpSubmitting}
                      data-testid={tid("create-emp-job")}
                    >
                      <option value="">-- 选择岗位 --</option>
                      {jobPresets.map((j) => (
                        <option key={j.label} value={j.label}>{j.label}</option>
                      ))}
                    </select>
                  </label>

                  {createEmpJob && (
                    <div className="admin-form-hint" style={{ fontSize: "0.85rem", color: "#666", marginTop: -4 }}>
                      内部角色: {selectedJobPreset()?.bamboo_role ?? "—"}
                      {selectedJobPreset()?.web_roles?.length ? ` · Web 角色: ${selectedJobPreset()!.web_roles.join(", ")}` : ""}
                    </div>
                  )}
                </div>
              )}

              {/* Step 2: Account */}
              {createStep === "account" && (
                <div className="wizard-step-body">
                  <label>
                    初始 PIN *
                    <input
                      type="password"
                      value={createEmpPin}
                      onChange={(e) => setCreateEmpPin(e.target.value.replace(/\D/g, ""))}
                      placeholder="至少 4 位数字"
                      maxLength={12}
                      disabled={createEmpSubmitting}
                      inputMode="numeric"
                      data-testid={tid("create-emp-pin")}
                    />
                    <span className="admin-form-hint" style={{ fontSize: "0.8rem", color: "#8593a8" }}>
                      员工登录 Bamboo 移动端的初始密码
                    </span>
                  </label>

                  <label className="admin-checkbox-label">
                    <input
                      type="checkbox"
                      checked={createEmpActive}
                      onChange={(e) => setCreateEmpActive(e.target.checked)}
                      disabled={createEmpSubmitting}
                      data-testid={tid("create-emp-active")}
                    />
                    <span>创建后立即启用</span>
                  </label>
                  {!createEmpActive && (
                    <p className="admin-form-hint" style={{ fontSize: "0.8rem", color: "#d97706" }}>
                      员工将以停用状态创建，后续可手动启用。
                    </p>
                  )}
                </div>
              )}

              {/* Step 3: Confirm */}
              {createStep === "confirm" && (
                <div className="wizard-step-body wizard-confirm">
                  <h4 style={{ margin: "0 0 12px", fontSize: "14px", color: "#42566f" }}>确认新增员工信息</h4>
                  <div className="wizard-confirm-grid">
                    <div className="wizard-confirm-row">
                      <span className="wizard-confirm-label">工号</span>
                      <span className="wizard-confirm-value">{createEmpCode}</span>
                    </div>
                    <div className="wizard-confirm-row">
                      <span className="wizard-confirm-label">姓名</span>
                      <span className="wizard-confirm-value">{createEmpName}</span>
                    </div>
                    <div className="wizard-confirm-row">
                      <span className="wizard-confirm-label">工厂</span>
                      <span className="wizard-confirm-value">
                        {(adminFactories.length > 0 ? adminFactories : factories).find((f) => f.factory_id === createEmpFactory)?.name || createEmpFactory}
                      </span>
                    </div>
                    <div className="wizard-confirm-row">
                      <span className="wizard-confirm-label">岗位</span>
                      <span className="wizard-confirm-value">{createEmpJob}</span>
                    </div>
                    <div className="wizard-confirm-row">
                      <span className="wizard-confirm-label">内部角色</span>
                      <span className="wizard-confirm-value">{selectedJobPreset()?.bamboo_role ?? "—"}</span>
                    </div>
                    <div className="wizard-confirm-row">
                      <span className="wizard-confirm-label">Web 角色</span>
                      <span className="wizard-confirm-value">{selectedJobPreset()?.web_roles?.join(", ") || "无"}</span>
                    </div>
                    <div className="wizard-confirm-row">
                      <span className="wizard-confirm-label">账号状态</span>
                      <span className="wizard-confirm-value">{createEmpActive ? "启用" : "停用"}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <footer style={{ display: "flex", gap: 8, justifyContent: "space-between" }}>
              <div>
                {createStep !== "identity" && (
                  <button
                    type="button"
                    className="btn secondary"
                    disabled={createEmpSubmitting}
                    onClick={() => {
                      setCreateEmpError("");
                      if (createStep === "account") setCreateStep("identity");
                      else if (createStep === "confirm") setCreateStep("account");
                    }}
                    data-testid={tid("create-wizard-back")}
                  >
                    上一步
                  </button>
                )}
              </div>
              <div style={{ display: "flex", gap: 8 }}>
                <button type="button" className="btn secondary" disabled={createEmpSubmitting} onClick={() => setShowCreateForm(false)}>取消</button>
                {createStep === "identity" && (
                  <button
                    type="button"
                    className="btn primary"
                    disabled={!canAdvanceFromIdentity() || createEmpSubmitting}
                    onClick={() => { setCreateEmpError(""); setCreateStep("account"); }}
                    data-testid={tid("create-wizard-next-identity")}
                  >
                    下一步
                  </button>
                )}
                {createStep === "account" && (
                  <button
                    type="button"
                    className="btn primary"
                    disabled={!canAdvanceFromAccount() || createEmpSubmitting}
                    onClick={() => { setCreateEmpError(""); setCreateStep("confirm"); }}
                    data-testid={tid("create-wizard-next-account")}
                  >
                    下一步
                  </button>
                )}
                {createStep === "confirm" && (
                  <button
                    type="button"
                    className="btn primary"
                    disabled={createEmpSubmitting}
                    onClick={() => void submitCreateEmployee()}
                    data-testid={tid("create-emp-submit")}
                  >
                    {createEmpSubmitting ? "创建中…" : "确认创建"}
                  </button>
                )}
              </div>
            </footer>
          </div>
        </div>
      )}
    </section>
  );
}

// ── Utility ──────────────────────────────────────────────────────

function formatLastLogin(raw: string): string {
  if (!raw) return "—";
  try {
    const d = new Date(raw);
    if (isNaN(d.getTime())) return raw;
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (diffDays === 0) return "今天";
    if (diffDays === 1) return "昨天";
    if (diffDays < 7) return `${diffDays} 天前`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} 周前`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} 个月前`;
    return d.toLocaleDateString("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit" });
  } catch {
    return raw;
  }
}
