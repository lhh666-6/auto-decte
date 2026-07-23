import { useEffect, useState } from "react";

import { listManagedForms } from "./api";
import type { ManagedFormVersion } from "./types";
import "./managed-forms.css";

export function PlantFormsPage() {
  const [items, setItems] = useState<ManagedFormVersion[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listManagedForms("plant")
      .then((result) => setItems(result.items))
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "加载失败"));
  }, []);

  return (
    <section className="managed-forms-page">
      <header className="managed-page-heading">
        <div>
          <h1>本厂表单</h1>
          <p>以下为管理员已对本厂启用的表单版本，仅供查看。</p>
        </div>
      </header>
      {error && <div role="alert" className="error-banner">{error}</div>}
      <div className="managed-form-list">
        {items.map((item) => (
          <article key={item.version_id} className="managed-form-card">
            <div className="managed-card-title">
              <h2>{item.name}</h2>
              <span className="managed-status">只读</span>
            </div>
            <p>{item.form_key} · 版本 {item.version}</p>
            <ul>
              {item.schema_json.fields?.map((field) => (
                <li key={field.key}>{field.label}（{field.type}）</li>
              ))}
            </ul>
          </article>
        ))}
        {!items.length && <p>本厂当前没有已启用表单。</p>}
      </div>
    </section>
  );
}
