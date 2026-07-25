import { useEffect, useMemo, useState } from "react";

interface FormDef {
  definition_id: string; form_key: string; name: string;
  owner_role: string; created_by: string; created_at: string;
  latest_version?: { version_id: string; version: number; status: string;
    schema_json: Record<string, unknown>; created_at: string; };
}

const FORM_LABELS: Record<string, string> = { SORTING: "《竹丝装笼跟踪牌》", DIPPING_DRYING: "《竹丝浸胶干燥生产记录表》" };
const STATUS_LABELS: Record<string, string> = { DRAFT: "草稿", PENDING_APPROVAL: "待审批", APPROVED: "已发布", REJECTED: "已驳回", RETIRED: "已退役" };

function fieldNames(schema: Record<string, unknown>): string {
  const fields = schema.fields as Array<{ label: string }> | undefined;
  return fields?.map(f => f.label).join("、") || "—";
}

export function AdminBusinessFormsPage() {
  const [forms, setForms] = useState<FormDef[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  function load() {
    setLoading(true); setError("");
    fetch("/api/v1/admin/form-definitions", { credentials: "include" })
      .then(r => { if (!r.ok) throw new Error(`请求失败 (${r.status})`); return r.json(); })
      .then((d: { items: FormDef[] }) => setForms(d.items ?? []))
      .catch(c => setError(c instanceof Error ? c.message : "加载失败"))
      .finally(() => setLoading(false));
  }
  useEffect(() => { load(); }, []);

  // Group by form_key so each definition gets one card.
  // If the API returns multiple versions per definition the extra rows appear
  // in an expandable version-history list inside the card.
  const groups = useMemo(() => {
    const map = new Map<string, FormDef[]>();
    forms.forEach(f => {
      const arr = map.get(f.form_key) || [];
      arr.push(f);
      map.set(f.form_key, arr);
    });
    return Array.from(map.entries()).map(([key, items]) => {
      // sort descending so items[0] is the highest version
      items.sort((a, b) => (b.latest_version?.version ?? 0) - (a.latest_version?.version ?? 0));
      return { key, items, primary: items[0], count: items.length };
    });
  }, [forms]);

  const toggleExpand = (key: string) => setExpanded(prev => ({ ...prev, [key]: !prev[key] }));

  return (
    <section className="admin-factories-page">
      <h1 className="admin-page-title">正式业务表单</h1>
      <p className="admin-page-subtitle">管理《竹丝装笼跟踪牌》和《竹丝浸胶干燥生产记录表》的版本与发布</p>

      {loading ? (
        <div className="empty-state" role="status">正在加载…</div>
      ) : error ? (
        <div className="empty-state" role="alert">
          <p>{error}</p>
          <button type="button" className="primary-button" onClick={load}>重试</button>
        </div>
      ) : groups.length === 0 ? (
        <div className="empty-state">暂无表单定义</div>
      ) : (
        <div className="bp-card-grid" style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(380px, 1fr))", gap: "1rem" }}>
          {groups.map(g => {
            const f = g.primary;
            const displayName = FORM_LABELS[g.key] || f.name;
            const statusKey = f.latest_version?.status ?? "";
            return (
              <div key={g.key} className="bp-card" style={{ borderLeft: g.key === "SORTING" ? "4px solid #16a34a" : "4px solid #2563eb" }}>
                <header className="bp-card-header">
                  <h2>{displayName}</h2>
                  <span className="bp-card-badge">{STATUS_LABELS[statusKey] ?? statusKey}</span>
                </header>
                <div className="bp-card-desc">
                  <p>版本: V{f.latest_version?.version ?? "—"}</p>
                  {f.latest_version?.schema_json && (
                    <p>业务字段: {fieldNames(f.latest_version.schema_json)}</p>
                  )}
                  {(() => {
                    const dep = (f.latest_version?.schema_json as Record<string, unknown> | undefined)?.depends_on;
                    if (!dep) return null;
                    return <p>依赖: {FORM_LABELS[String(dep)] || String(dep)}</p>;
                  })()}
                  <p className="signature-muted">创建: {f.created_at ? new Date(f.created_at).toLocaleDateString() : "—"}</p>

                  {g.count > 1 && (
                    <div style={{ marginTop: "0.5rem" }}>
                      <button type="button" className="secondary-button"
                        onClick={() => toggleExpand(g.key)}>
                        {expanded[g.key] ? "收起版本历史" : `查看全部版本 (${g.count})`}
                      </button>
                      {expanded[g.key] && (
                        <ul style={{ marginTop: "0.5rem", paddingLeft: "1.2rem", fontSize: "0.9rem" }}>
                          {g.items.map(v => (
                            <li key={v.definition_id}>
                              V{v.latest_version?.version ?? "—"} · {STATUS_LABELS[v.latest_version?.status ?? ""] ?? v.latest_version?.status ?? "—"}
                              <span className="signature-muted"> · {v.created_at ? new Date(v.created_at).toLocaleDateString() : "—"}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
