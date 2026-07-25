import { useEffect, useState } from "react";

interface FactoryInfo {
  factory_id: string;
  code: string;
  factory_code: string | null;
  name: string;
  active: boolean;
}

interface JobPreset {
  label: string;
  bamboo_role: string;
  web_roles: string[];
}

export function AdminFactoriesPage() {
  const [factories, setFactories] = useState<FactoryInfo[]>([]);
  const [jobPresets, setJobPresets] = useState<JobPreset[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [tab, setTab] = useState<"factories" | "jobs">("factories");

  // ── Create factory modal ──
  const [showCreateFactory, setShowCreateFactory] = useState(false);
  const [newFactoryName, setNewFactoryName] = useState("");
  const [newFactoryCode, setNewFactoryCode] = useState("");
  const [activateForms, setActivateForms] = useState<string[]>([]);
  const [createFactorySubmitting, setCreateFactorySubmitting] = useState(false);
  const [createFactoryError, setCreateFactoryError] = useState("");
  const [createFactorySuccess, setCreateFactorySuccess] = useState("");

  function getCsrfToken(): string {
    if (typeof document === "undefined") return "";
    const prefix = "web_csrf=";
    const item = document.cookie.split(";").map(p => p.trim()).find(p => p.startsWith(prefix));
    return item ? decodeURIComponent(item.slice(prefix.length)) : "";
  }

  function loadData() {
    setLoading(true);
    setError("");
    Promise.all([
      fetch("/api/v1/admin/factories-all", { credentials: "include" }).then((r) => {
        if (!r.ok) throw new Error(`加载工厂失败 (${r.status})`);
        return r.json();
      }),
      fetch("/api/v1/admin/job-presets", { credentials: "include" }).then((r) => {
        if (!r.ok) throw new Error(`加载岗位失败 (${r.status})`);
        return r.json();
      }),
    ])
      .then(([fData, jData]) => {
        setFactories((fData as { items: FactoryInfo[] }).items ?? []);
        setJobPresets((jData as { items: JobPreset[] }).items ?? []);
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "加载失败"))
      .finally(() => setLoading(false));
  }
  useEffect(() => { loadData(); }, []);

  async function handleCreateFactory() {
    if (!newFactoryName.trim()) { setCreateFactoryError("请输入工厂名称"); return; }
    setCreateFactorySubmitting(true);
    setCreateFactoryError("");
    setCreateFactorySuccess("");
    try {
      const csrf = getCsrfToken();
      const resp = await fetch("/api/v1/admin/factories", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify({
          name: newFactoryName.trim(),
          code: newFactoryCode.trim() || undefined,
          activate_forms: activateForms,
        }),
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({})) as { detail?: { detail?: string } };
        throw new Error(err.detail?.detail ?? `创建失败 (${resp.status})`);
      }
      const result = await resp.json() as FactoryInfo;
      setCreateFactorySuccess(`工厂 ${result.name} (${result.factory_code || result.code}) 创建成功`);
      setNewFactoryName("");
      setNewFactoryCode("");
      await loadData();
      setTimeout(() => { setShowCreateFactory(false); setCreateFactorySuccess(""); }, 2000);
    } catch (cause: unknown) {
      setCreateFactoryError(cause instanceof Error ? cause.message : "创建失败");
    } finally {
      setCreateFactorySubmitting(false);
    }
  }

  async function handleToggleFactory(factoryId: string, activate: boolean) {
    const endpoint = activate
      ? `/api/v1/admin/factories/${encodeURIComponent(factoryId)}/activate`
      : `/api/v1/admin/factories/${encodeURIComponent(factoryId)}/deactivate`;
    try {
      const resp = await fetch(endpoint, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": getCsrfToken() },
      });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({})) as { detail?: { detail?: string } };
        throw new Error(err.detail?.detail ?? `操作失败 (${resp.status})`);
      }
      await loadData();
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "操作失败");
    }
  }

  const WEB_ROLE_LABELS: Record<string, string> = {
    ADMIN: "系统管理员", FINANCE: "财务审批", PLANT_MANAGER: "厂长",
  };
  function payrollModeFor(role: string): string {
    return ["PLANT_MANAGER", "SUPERVISOR", "SYSTEM_ADMIN", "FINANCE_APPROVER"].includes(role)
      ? "固定管理工资" : "生产计量工资";
  }

  return (
    <section className="admin-factories-page">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <div>
          <h1 className="admin-page-title" style={{ margin: 0 }}>工厂与岗位</h1>
          <p className="admin-page-subtitle" style={{ margin: "4px 0 0" }}>管理正式工厂和岗位预设</p>
        </div>
        {tab === "factories" && (
          <button type="button" className="primary-button" onClick={() => setShowCreateFactory(true)}>
            + 新建工厂
          </button>
        )}
      </div>

      {error && <div className="banner danger" role="alert" style={{ marginTop: 12 }}>{error}</div>}

      <div className="admin-factory-tabs" style={{ display: "flex", gap: 0, marginTop: 16 }}>
        <button
          type="button"
          className={`btn ${tab === "factories" ? "primary" : "secondary"}`}
          onClick={() => setTab("factories")}
        >
          工厂 ({factories.length})
        </button>
        <button
          type="button"
          className={`btn ${tab === "jobs" ? "primary" : "secondary"}`}
          onClick={() => setTab("jobs")}
        >
          岗位预设 ({jobPresets.length})
        </button>
      </div>

      {loading ? (
        <div className="empty-state">加载中…</div>
      ) : tab === "factories" ? (
        factories.length === 0 ? (
          <div className="empty-state">
            <p>暂无工厂数据</p>
            <button type="button" className="primary-button" onClick={() => setShowCreateFactory(true)} style={{ marginTop: 8 }}>
              + 新建第一个工厂
            </button>
          </div>
        ) : (
          <div className="governed-table-wrap">
            <table className="governed-table">
              <thead>
                <tr>
                  <th>工厂代码</th>
                  <th>工厂名称</th>
                  <th>状态</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {factories.map((f) => (
                  <tr key={f.factory_id} style={{ opacity: f.active ? 1 : 0.5 }}>
                    <td><code>{f.factory_code || f.code}</code></td>
                    <td>{f.name}</td>
                    <td>
                      <span className={f.active ? "badge badge-active" : "badge badge-inactive"}
                        style={{
                          display: "inline-block", padding: "2px 8px", borderRadius: 12,
                          fontSize: "0.8rem", fontWeight: 500,
                          background: f.active ? "#dcfce7" : "#f1f5f9",
                          color: f.active ? "#166534" : "#64748b",
                        }}>
                        {f.active ? "启用" : "停用"}
                      </span>
                    </td>
                    <td>
                      {f.active ? (
                        <button type="button" className="btn secondary"
                          onClick={() => void handleToggleFactory(f.factory_id, false)}
                          style={{ fontSize: "0.85rem" }}>
                          停用
                        </button>
                      ) : (
                        <button type="button" className="btn secondary"
                          onClick={() => void handleToggleFactory(f.factory_id, true)}
                          style={{ fontSize: "0.85rem" }}>
                          恢复
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      ) : (
        jobPresets.length === 0 ? (
          <div className="empty-state">暂无岗位预设</div>
        ) : (
          <div className="governed-table-wrap">
            <table className="governed-table">
              <thead>
                <tr>
                  <th>岗位名称</th>
                  <th>系统角色</th>
                  <th>工资模式</th>
                  <th>Web 权限</th>
                </tr>
              </thead>
              <tbody>
                {jobPresets.map((j) => (
                  <tr key={j.label}>
                    <td>{j.label}</td>
                    <td><code>{j.bamboo_role}</code></td>
                    <td>{payrollModeFor(j.bamboo_role)}</td>
                    <td>{j.web_roles.map((r) => WEB_ROLE_LABELS[r] ?? r).join(", ") || "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {/* ── Create Factory Modal ── */}
      {showCreateFactory && (
        <div className="modal-backdrop" role="presentation" onClick={() => !createFactorySubmitting && setShowCreateFactory(false)}>
          <div
            className="modal-panel"
            role="dialog"
            aria-modal="true"
            aria-labelledby="createFactoryTitle"
            onClick={(e) => e.stopPropagation()}
          >
            <header>
              <h3 id="createFactoryTitle">新建工厂</h3>
              <button type="button" disabled={createFactorySubmitting} onClick={() => setShowCreateFactory(false)} aria-label="关闭">×</button>
            </header>
            <div className="modal-body">
              {createFactorySuccess && (
                <div className="banner success" role="status">{createFactorySuccess}</div>
              )}
              {createFactoryError && (
                <div className="banner danger" role="alert">{createFactoryError}</div>
              )}
              <label>
                工厂名称 *
                <input
                  type="text"
                  value={newFactoryName}
                  onChange={(e) => setNewFactoryName(e.target.value)}
                  placeholder="例如 第一生产厂"
                  disabled={createFactorySubmitting}
                />
              </label>
              <label style={{ marginTop: 12 }}>
                工厂代码（留空自动生成）
                <input
                  type="text"
                  value={newFactoryCode}
                  onChange={(e) => setNewFactoryCode(e.target.value)}
                  placeholder="例如 F003"
                  disabled={createFactorySubmitting}
                  style={{ fontFamily: "monospace" }}
                />
                <span className="admin-form-hint" style={{ fontSize: "0.8rem", color: "#8593a8" }}>
                  系统自动生成 F001, F002, F003… 创建后不可修改
                </span>
              </label>
              <fieldset style={{ marginTop: 16, border: "1px solid #e2e8f0", borderRadius: 8, padding: "12px 16px" }}>
                <legend style={{ fontSize: "0.9rem", fontWeight: 600, color: "#334155" }}>启用业务表单</legend>
                {(["SORTING", "DIPPING_DRYING"] as const).map((fk) => (
                  <label key={fk} style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 8, cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={activateForms.includes(fk)}
                      onChange={(e) => {
                        setActivateForms(prev =>
                          e.target.checked ? [...prev, fk] : prev.filter((k) => k !== fk)
                        );
                      }}
                    />
                    <span>{fk === "SORTING" ? "《竹丝装笼跟踪牌》" : "《竹丝浸胶干燥生产记录表》"}</span>
                  </label>
                ))}
              </fieldset>
            </div>
            <footer style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" className="btn secondary" disabled={createFactorySubmitting} onClick={() => setShowCreateFactory(false)}>取消</button>
              <button type="button" className="btn primary" disabled={createFactorySubmitting || !newFactoryName.trim()}
                onClick={() => void handleCreateFactory()}>
                {createFactorySubmitting ? "创建中…" : "确认创建"}
              </button>
            </footer>
          </div>
        </div>
      )}
    </section>
  );
}
