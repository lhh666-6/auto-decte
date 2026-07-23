import { useEffect, useState } from "react";

import {
  activateManagedForm,
  decideManagedFormApproval,
  listManagedFormApprovals,
} from "./api";
import type { ManagedFormVersion } from "./types";
import "./managed-forms.css";

export function AdminFormApprovalsPage() {
  const [items, setItems] = useState<ManagedFormVersion[]>([]);
  const [factoryInput, setFactoryInput] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    listManagedFormApprovals()
      .then((result) => setItems(result.items))
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "加载失败"));
  }, []);

  async function decide(item: ManagedFormVersion, decision: "APPROVE" | "REJECT") {
    try {
      const updated = await decideManagedFormApproval(item.version_id, decision);
      setItems((current) => current.map((value) => (
        value.version_id === updated.version_id ? updated : value
      )));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "审核失败");
    }
  }

  async function activate(item: ManagedFormVersion) {
    const plantIds = factoryInput.split(",").map((value) => value.trim()).filter(Boolean);
    try {
      await activateManagedForm(item.version_id, plantIds);
      setItems((current) => current.filter((value) => value.version_id !== item.version_id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "启用失败");
    }
  }

  return (
    <section className="managed-forms-page">
      <header className="managed-page-heading">
        <div>
          <h1>表单审核与启用</h1>
          <p>审核内容版本，并明确选择需要启用的工厂。</p>
        </div>
      </header>
      {error && <div role="alert" className="error-banner">{error}</div>}
      <div className="managed-form-list">
        {items.map((item) => (
          <article key={item.version_id} className="managed-form-card">
            <h2>{item.name}</h2>
            <p>{item.form_key} · 版本 {item.version} · {item.schema_json.fields?.length ?? 0} 个字段</p>
            {item.status === "PENDING_APPROVAL" ? (
              <div className="managed-form-actions">
                <button type="button" onClick={() => void decide(item, "APPROVE")}>批准版本</button>
                <button type="button" onClick={() => void decide(item, "REJECT")}>退回修改</button>
              </div>
            ) : (
              <div className="managed-activation-panel">
                <label>
                  启用工厂
                  <input
                    aria-label="启用工厂"
                    placeholder="多个工厂用逗号分隔"
                    value={factoryInput}
                    onChange={(event) => setFactoryInput(event.target.value)}
                  />
                </label>
                <button type="button" onClick={() => void activate(item)}>按工厂启用</button>
              </div>
            )}
          </article>
        ))}
        {!items.length && <p>当前没有待审核表单。</p>}
      </div>
    </section>
  );
}
