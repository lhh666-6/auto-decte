import { useEffect, useState } from "react";

interface FormDef {
  definition_id: string; form_key: string; name: string;
  owner_role: string; created_by: string; created_at: string;
  latest_version?: { version_id: string; version: number; status: string;
    schema_json: Record<string, unknown>; created_at: string; };
}

const FORM_LABELS: Record<string, string> = { SORTING: "《竹丝装笼跟踪牌》", DIPPING_DRYING: "《配片数计量考核表》" };
const STATUS_LABELS: Record<string, string> = { DRAFT: "草稿", PENDING_APPROVAL: "待审批", APPROVED: "已发布", REJECTED: "已驳回", RETIRED: "已退役" };

function fieldNames(schema: Record<string, unknown>): string {
  const fields = schema.fields as Array<{ label: string }> | undefined;
  return fields?.map(f => f.label).join("、") || "—";
}

export function AdminBusinessFormsPage() {
  const [forms, setForms] = useState<FormDef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    setLoading(true); setError("");
    fetch("/api/v1/admin/form-definitions", { credentials: "include" })
      .then(r => r.json()).then((d: { items: FormDef[] }) => setForms(d.items ?? []))
      .catch(c => setError(c instanceof Error ? c.message : "加载失败"))
      .finally(() => setLoading(false));
  }, []);

  return (
    <section className="admin-factories-page">
      <h1 className="admin-page-title">正式业务表单</h1>
      <p className="admin-page-subtitle">管理《竹丝装笼跟踪牌》和《配片数计量考核表》的版本与发布</p>
      {error && <div className="banner danger" role="alert">{error}</div>}
      {loading ? (
        <div className="empty-state">加载中…</div>
      ) : forms.length === 0 ? (
        <div className="empty-state">暂无表单定义</div>
      ) : (
        <div className="bp-card-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))", gap: "1rem" }}>
          {forms.map(f => (
            <div key={f.definition_id} className="bp-card" style={{ borderLeft: f.form_key === "SORTING" ? "4px solid #16a34a" : "4px solid #2563eb" }}>
              <header className="bp-card-header">
                <h2>{f.name}</h2>
                <span className="bp-card-badge">{STATUS_LABELS[f.latest_version?.status ?? ""] ?? f.latest_version?.status}</span>
              </header>
              <div className="bp-card-desc">
                <p>标识: <code>{f.form_key}</code></p>
                <p>版本: V{f.latest_version?.version ?? "—"}</p>
                {f.latest_version?.schema_json && (
                  <p>业务字段: {fieldNames(f.latest_version.schema_json)}</p>
                )}
                {(() => { const dep = (f.latest_version?.schema_json as Record<string, unknown> | undefined)?.depends_on; if (!dep) return null; return <p>依赖: {FORM_LABELS[String(dep)] || String(dep)}</p>; })()}
                <p className="signature-muted">创建: {f.created_at ? new Date(f.created_at).toLocaleDateString() : "—"}</p>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
