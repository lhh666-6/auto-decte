import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  createManagedForm,
  listManagedForms,
  submitManagedFormApproval,
  updateManagedForm,
} from "./api";
import type { ManagedFormField, ManagedFormVersion } from "./types";
import "./managed-forms.css";

const STATUS_LABELS: Record<string, string> = {
  DRAFT: "草稿",
  PENDING_APPROVAL: "待管理员审核",
  APPROVED: "已批准",
  REJECTED: "已退回",
};

export function FinanceFormsPage() {
  const [items, setItems] = useState<ManagedFormVersion[]>([]);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ManagedFormVersion | null>(null);
  const [fields, setFields] = useState<ManagedFormField[]>([
    { key: "", label: "", type: "text", required: true },
  ]);
  const [error, setError] = useState("");

  useEffect(() => {
    listManagedForms("finance")
      .then((result) => setItems(result.items))
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "加载失败"));
  }, []);

  function openCreate() {
    setEditing(null);
    setFields([{ key: "", label: "", type: "text", required: true }]);
    setCreating(true);
  }

  function openEdit(item: ManagedFormVersion) {
    setEditing(item);
    setFields(item.schema_json.fields?.length
      ? item.schema_json.fields
      : [{ key: "", label: "", type: "text", required: true }]);
    setCreating(true);
  }

  function updateField(index: number, patch: Partial<ManagedFormField>) {
    setFields((current) => current.map((field, fieldIndex) => (
      fieldIndex === index ? { ...field, ...patch } : field
    )));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      const saved = editing
        ? await updateManagedForm(editing.version_id, editing.revision, { fields })
        : await createManagedForm({
            name: String(data.get("name") ?? "").trim(),
            form_key: String(data.get("form_key") ?? "").trim().toUpperCase(),
            owner_role: "WORKER",
            schema_json: { fields },
          });
      setItems((current) => editing
        ? current.map((item) => item.version_id === saved.version_id ? saved : item)
        : [saved, ...current]);
      setCreating(false);
      setEditing(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "保存失败");
    }
  }

  async function submit(item: ManagedFormVersion) {
    try {
      const updated = await submitManagedFormApproval(item.version_id);
      setItems((current) => current.map((value) => (
        value.version_id === updated.version_id ? updated : value
      )));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "提交失败");
    }
  }

  return (
    <section className="managed-forms-page">
      <header className="managed-page-heading">
        <div>
          <h1>电子表单设计</h1>
          <p>以字段卡片创建草稿，审核通过后由管理员按工厂启用。</p>
        </div>
        <button type="button" onClick={openCreate}>新建电子表单</button>
      </header>
      {error && <div role="alert" className="error-banner">{error}</div>}
      {creating && (
        <form className="managed-form-editor" onSubmit={save}>
          <h2>{editing ? `编辑 ${editing.name}` : "新建表单草稿"}</h2>
          <label>
            表单名称
            <input
              name="name"
              aria-label="表单名称"
              defaultValue={editing?.name}
              disabled={Boolean(editing)}
              required
            />
          </label>
          <label>
            表单标识
            <input
              name="form_key"
              aria-label="表单标识"
              defaultValue={editing?.form_key}
              disabled={Boolean(editing)}
              required
            />
          </label>
          <fieldset>
            <legend>表单字段</legend>
            {fields.map((field, index) => (
              <div className="managed-field-row" key={index}>
                <label>
                  字段名称
                  <input
                    aria-label="字段名称"
                    value={field.label}
                    onChange={(event) => updateField(index, { label: event.target.value })}
                    required
                  />
                </label>
                <label>
                  字段标识
                  <input
                    aria-label="字段标识"
                    value={field.key}
                    onChange={(event) => updateField(index, { key: event.target.value })}
                    required
                  />
                </label>
                <label>
                  字段类型
                  <select
                    aria-label="字段类型"
                    value={field.type}
                    onChange={(event) => updateField(index, { type: event.target.value })}
                  >
                    <option value="text">文本</option>
                    <option value="number">数字</option>
                    <option value="date">日期</option>
                  </select>
                </label>
                {fields.length > 1 && (
                  <button
                    type="button"
                    onClick={() => setFields((current) => current.filter((_, i) => i !== index))}
                  >
                    删除字段
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={() => setFields((current) => [
                ...current,
                { key: "", label: "", type: "text", required: true },
              ])}
            >
              添加字段
            </button>
          </fieldset>
          <div className="managed-form-actions">
            <button type="submit">保存草稿</button>
            <button type="button" onClick={() => {
              setCreating(false);
              setEditing(null);
            }}>取消</button>
          </div>
        </form>
      )}
      <div className="managed-form-list">
        {items.map((item) => (
          <article key={item.version_id} className="managed-form-card">
            <div>
              <h2>{item.name}</h2>
              <p>{item.form_key} · 版本 {item.version}</p>
            </div>
            <span className={`managed-status managed-status-${item.status.toLowerCase()}`}>
              {STATUS_LABELS[item.status] ?? item.status}
            </span>
            <p>{item.schema_json.fields?.length ?? 0} 个字段</p>
            {item.status === "DRAFT" && (
              <div className="managed-form-actions">
                <button type="button" onClick={() => openEdit(item)}>编辑草稿</button>
                <button type="button" onClick={() => void submit(item)}>提交管理员审核</button>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
