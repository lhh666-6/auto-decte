import { useEffect, useState } from "react";

import { listManagedForms } from "./api";
import type { ManagedFormVersion } from "./types";
import "./managed-forms.css";

export function PlantFormsPage() {
  const [items, setItems] = useState<ManagedFormVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    setError("");
    listManagedForms("plant")
      .then((result) => { setItems(result.items); setLoading(false); })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "表单加载失败");
        setLoading(false);
      });
  }
  useEffect(load, []);

  return (
    <section className="managed-forms-page">
      <header className="managed-page-heading">
        <div>
          <h1>本厂表单</h1>
          <p>以下为管理员已对本厂启用的表单版本，仅供查看。</p>
        </div>
      </header>
      {loading && <div role="status">正在加载表单…</div>}
      {error && (
        <div role="alert" className="error-banner">
          {error}{" "}
          <button type="button" onClick={load}>重试</button>
        </div>
      )}
      {!loading && !error && items.length === 0 && (
        <p>管理员尚未向本厂启用表单。</p>
      )}
      {!loading && !error && items.length > 0 && (
        <div className="managed-form-list">
          {items.map((item) => (
            <article key={item.version_id} className="managed-form-card">
              <div className="managed-card-title">
                <h2>{item.name}</h2>
                <span className="managed-status">只读</span>
              </div>
              <p className="signature-muted"><small>{item.form_key} · 版本 {item.version}</small></p>
              <ul>
                {item.schema_json.fields?.map((field) => (
                  <li key={field.key}>{field.label} <small className="signature-muted">（{field.type}）</small></li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
