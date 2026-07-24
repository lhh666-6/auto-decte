import { useCallback, useEffect, useMemo, useState } from "react";
import "./workspace.css";

/* ------------------------------------------------------------------ */
/*  types                                                             */
/* ------------------------------------------------------------------ */

type ExceptionCategory =
  | "PRE_CHECK_FAILED"
  | "REFERENCE_CONFLICT"
  | "ACTIVATION_EXCEPTION"
  | "EXPORT_MAPPING_EXCEPTION"
  | "PAYROLL_RULE_EXCEPTION";

interface VersionException {
  exception_id: string;
  category: ExceptionCategory;
  object_type: string;
  object_name: string;
  object_id: string;
  factory_id: string;
  factory_name: string;
  discovered_at?: string;
  status: "OPEN" | "ACKNOWLEDGED" | "RESOLVED";
  reference_chain?: string[];
  impact_scope?: {
    factories: string[];
    affected_objects: number;
    affected_records: number;
  };
  recommended_action: string;
  pre_check_errors?: string[];
  detail_summary: string;
}

const STATUS_LABELS: Record<string, string> = {
  OPEN: "待处理", ACKNOWLEDGED: "已知悉", RESOLVED: "已解决",
};

const CATEGORY_LABELS: Record<string, string> = {
  PRE_CHECK_FAILED: "预检失败", REFERENCE_CONFLICT: "引用冲突",
  ACTIVATION_EXCEPTION: "启用异常", EXPORT_MAPPING_EXCEPTION: "导出映射异常",
  PAYROLL_RULE_EXCEPTION: "工资规则异常",
};

function extractFactoryOptions(exceptions: VersionException[]): string[] {
  const seen = new Set<string>();
  for (const ex of exceptions) {
    if (ex.factory_id) seen.add(ex.factory_id);
  }
  return [...seen].sort();
}

/* ------------------------------------------------------------------ */
/*  page component                                                    */
/* ------------------------------------------------------------------ */

export function AdminVersionExceptionsPage() {
  const [exceptions, setExceptions] = useState<VersionException[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [categoryFilter, setCategoryFilter] = useState<ExceptionCategory | "ALL">("ALL");
  const [factoryFilter, setFactoryFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState<VersionException["status"] | "ALL">("ALL");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [search, setSearch] = useState("");

  const fetchExceptions = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      // Derive version exceptions from real administrative data:
      // form approvals, workflow approvals, and payroll rule approvals.
      const [formResp, wfResp, payrollResp] = await Promise.all([
        fetch("/api/v1/admin/form-approvals", { credentials: "include" }),
        fetch("/api/v1/admin/workflow-approvals", { credentials: "include" }),
        fetch("/api/v1/admin/payroll-approvals", { credentials: "include" }),
      ]);
      if (!formResp.ok || !wfResp.ok || !payrollResp.ok) {
        throw new Error("部分版本数据暂不可用");
      }
      const formData = await formResp.json() as { items?: Array<{ version_id: string; name?: string; status: string; factory_id?: string }> };
      const wfData = await wfResp.json() as { items?: Array<{ version_id: string; name?: string; status: string; factory_id?: string }> };
      const payrollData = await payrollResp.json() as { items?: Array<Record<string,string>> };

      const exceptions: VersionException[] = [];
      // Rejected versions
      for (const item of [...(formData.items ?? []), ...(wfData.items ?? [])]) {
        if (item.status === "REJECTED") {
          exceptions.push({
            exception_id: `rej-${item.version_id}`,
            category: "PRE_CHECK_FAILED",
            object_type: "版本",
            object_name: (item as Record<string,string>).name ?? item.version_id,
            object_id: item.version_id,
            factory_id: item.factory_id ?? "",
            factory_name: item.factory_id ?? "",
            status: "OPEN",
            recommended_action: "查看驳回原因，修复后重新提交审批",
            detail_summary: "该版本已被管理员驳回，需要修复问题后重新提交",
          });
        }
      }
      // Payroll rule exceptions
      for (const item of (payrollData.items ?? [])) {
        if (item["status"] === "REJECTED" || item["status"] === "RETIRED") {
          exceptions.push({
            exception_id: `pay-${item["rule_version_id"]}`,
            category: "PAYROLL_RULE_EXCEPTION",
            object_type: "工资规则",
            object_name: item["rule_key"] ?? item["rule_version_id"],
            object_id: item["rule_version_id"],
            factory_id: item["factory_id"] ?? "",
            factory_name: item["factory_id"] ?? "",
            status: item["status"] === "REJECTED" ? "OPEN" : "RESOLVED",
            recommended_action: item["status"] === "REJECTED" ? "修复规则后重新提交管理员审批" : "规则已退役，历史数据保留",
            detail_summary: item["status"] === "REJECTED" ? "工资规则版本被管理员驳回" : "工资规则版本已退役",
          });
        }
      }
      setExceptions(exceptions.length > 0 ? exceptions : []);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "加载异常列表失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchExceptions();
  }, [fetchExceptions]);

  const filtered = useMemo(() => {
    return exceptions.filter((ex) => {
      if (categoryFilter !== "ALL" && ex.category !== categoryFilter) return false;
      if (factoryFilter && ex.factory_id !== factoryFilter) return false;
      if (statusFilter !== "ALL" && ex.status !== statusFilter) return false;
      if (search) {
        const term = search.toLowerCase();
        const matchName = ex.object_name.toLowerCase().includes(term);
        const matchSummary = ex.detail_summary.toLowerCase().includes(term);
        if (!matchName && !matchSummary) return false;
      }
      return true;
    });
  }, [exceptions, categoryFilter, factoryFilter, statusFilter, search]);

  /* ---------- loading / empty / error ---------- */
  if (loading) return <div role="status" className="page-loading">正在加载版本异常列表...</div>;
  if (error) return <div role="alert" className="error-banner">{error}</div>;

  return (
    <section className="version-exceptions-page">
      <header className="vex-header">
        <div>
          <h1>版本诊断</h1>
          <p>根据当前审批与版本状态即时派生，不作为独立正式业务记录。</p>
        </div>
      </header>

      {/* ---------- filters ---------- */}
      <div className="vex-filters">
        <label>
          异常类型
          <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value as ExceptionCategory | "ALL")}>
            <option value="ALL">全部</option>
            {(Object.keys(CATEGORY_LABELS) as ExceptionCategory[]).map((cat) => (
              <option key={cat} value={cat}>{CATEGORY_LABELS[cat]}</option>
            ))}
          </select>
        </label>
        <label>
          工厂
          <select value={factoryFilter} onChange={(e) => setFactoryFilter(e.target.value)}>
            <option value="">全部</option>
            {extractFactoryOptions(exceptions).map((f) => {
              const id = f; const name = f;
              return <option key={id} value={id}>{name}</option>;
            })}
          </select>
        </label>
        <label>
          状态
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as VersionException["status"] | "ALL")}>
            <option value="ALL">全部</option>
            {(Object.keys(STATUS_LABELS) as Array<VersionException["status"]>).map((s) => (
              <option key={s} value={s}>{STATUS_LABELS[s]}</option>
            ))}
          </select>
        </label>
        <label>
          搜索
          <input
            type="search"
            placeholder="按名称或描述搜索..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
      </div>

      {/* ---------- list ---------- */}
      {filtered.length === 0 ? (
        <p className="vex-empty">没有匹配的版本异常记录。</p>
      ) : (
        <div className="vex-list">
          {filtered.map((ex) => (
            <article
              key={ex.exception_id}
              className={`vex-card ${selectedId === ex.exception_id ? "vex-card-selected" : ""}`}
              onClick={() => setSelectedId(ex.exception_id === selectedId ? null : ex.exception_id)}
              role="button"
              tabIndex={0}
              onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") setSelectedId(ex.exception_id === selectedId ? null : ex.exception_id); }}
            >
              <div className="vex-card-header">
                <span className={`vex-category-badge vex-cat-${ex.category.toLowerCase()}`}>
                  {CATEGORY_LABELS[ex.category]}
                </span>
                <span className={`vex-status-badge vex-status-${ex.status.toLowerCase()}`}>
                  {STATUS_LABELS[ex.status]}
                </span>
              </div>
              <h3>{ex.object_name}</h3>
              <p className="vex-card-meta">
                <span>{ex.object_type}</span>
                <span>{ex.factory_name} ({ex.factory_id})</span>
                <span>当前诊断</span>
              </p>
              <p className="vex-card-summary">{ex.detail_summary}</p>

              {/* expanded detail */}
              {selectedId === ex.exception_id && (
                <div className="vex-detail">
                  {ex.reference_chain && ex.reference_chain.length > 0 && (
                    <div className="vex-detail-section">
                      <h4>引用链</h4>
                      <ol className="vex-reference-chain">
                        {ex.reference_chain.map((link, i) => (
                          <li key={`${ex.exception_id}-ref-${i}`}>{link}</li>
                        ))}
                      </ol>
                    </div>
                  )}

                  {ex.impact_scope && (
                    <div className="vex-detail-section">
                      <h4>影响范围</h4>
                      <p>涉及工厂：{ex.impact_scope.factories.join("、") || "无"}</p>
                      <p>受影响对象数：{ex.impact_scope.affected_objects}</p>
                      <p>受影响记录数：{ex.impact_scope.affected_records}</p>
                    </div>
                  )}

                  {ex.pre_check_errors && ex.pre_check_errors.length > 0 && (
                    <div className="vex-detail-section">
                      <h4>预检错误</h4>
                      <ul>
                        {ex.pre_check_errors.map((err, i) => (
                          <li key={`${ex.exception_id}-err-${i}`} className="vex-error-item">{err}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="vex-detail-section">
                    <h4>推荐处理动作</h4>
                    <p>{ex.recommended_action}</p>
                  </div>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
