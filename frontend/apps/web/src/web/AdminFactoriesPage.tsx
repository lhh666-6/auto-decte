import { useEffect, useState } from "react";

interface FactoryInfo {
  factory_id: string;
  code: string;
  name: string;
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

  useEffect(() => {
    setLoading(true);
    setError("");
    Promise.all([
      fetch("/api/v1/admin/factories", { credentials: "include" }).then((r) => r.json()),
      fetch("/api/v1/admin/job-presets", { credentials: "include" }).then((r) => r.json()),
    ])
      .then(([fData, jData]) => {
        setFactories((fData as { items: FactoryInfo[] }).items ?? []);
        setJobPresets((jData as { items: JobPreset[] }).items ?? []);
      })
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "加载失败"))
      .finally(() => setLoading(false));
  }, []);

  const WEB_ROLE_LABELS: Record<string, string> = {
    ADMIN: "系统管理员", FINANCE: "财务审批", PLANT_MANAGER: "厂长",
  };

  return (
    <section className="admin-factories-page">
      <h1 className="admin-page-title">工厂与岗位</h1>
      <p className="admin-page-subtitle">管理正式工厂和岗位预设</p>

      {error && <div className="banner danger" role="alert">{error}</div>}

      <div className="admin-factory-tabs" style={{ display: "flex", gap: 0, marginBottom: 16 }}>
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
          <div className="empty-state">暂无工厂数据</div>
        ) : (
          <div className="governed-table-wrap">
            <table className="governed-table">
              <thead>
                <tr>
                  <th>工厂名称</th>
                  <th>工厂 ID</th>
                  <th>编号</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {factories.map((f) => (
                  <tr key={f.factory_id}>
                    <td>{f.name}</td>
                    <td><code>{f.factory_id}</code></td>
                    <td><code>{f.code}</code></td>
                    <td><button type="button" className="btn secondary" disabled title="暂未开放">编辑</button></td>
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
                  <th>Bamboo Role</th>
                  <th>Web 角色</th>
                  <th>操作</th>
                </tr>
              </thead>
              <tbody>
                {jobPresets.map((j) => (
                  <tr key={j.label}>
                    <td>{j.label}</td>
                    <td><code>{j.bamboo_role}</code></td>
                    <td>{j.web_roles.map((r) => WEB_ROLE_LABELS[r] ?? r).join(", ") || "—"}</td>
                    <td><button type="button" className="btn secondary" disabled title="暂未开放">编辑</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}
    </section>
  );
}
