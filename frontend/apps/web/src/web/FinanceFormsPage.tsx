import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  createManagedForm,
  listManagedForms,
  submitManagedFormApproval,
  updateManagedForm,
} from "./api";
import type { ManagedFormField, ManagedFormVersion } from "./types";
import { StatusBadge, ReasonConfirmDialog, EmptyState, ErrorAlert, PageHeader } from "./shared";
import type { PreCheckResult } from "./shared";
import "./managed-forms.css";
import "./finance-pages.css";

function formatTime(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-CN");
  } catch {
    return iso;
  }
}

/** Actions allowed per status */
function allowedActions(status: string): string[] {
  switch (status) {
    case "DRAFT":
    case "READY_TO_SUBMIT":
      return ["edit", "preflight", "delete", "submit"];
    case "PENDING_APPROVAL":
      return ["view"];
    case "APPROVED":
      return ["view", "clone"];
    case "REJECTED":
      return ["view", "view_reason", "clone"];
    case "RETIRED":
      return ["view"];
    default:
      return ["view"];
  }
}

/** Preflight check on a form version */
function runPreflight(item: ManagedFormVersion): PreCheckResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const fields = item.schema_json.fields ?? [];

  if (!item.name || !item.name.trim()) errors.push("表单名称为空");
  if (!item.form_key || !item.form_key.trim()) errors.push("表单标识为空");
  if (fields.length === 0) errors.push("表单没有字段");
  else {
    const keys = new Set<string>();
    for (const f of fields) {
      if (!f.key || !f.key.trim()) errors.push("存在空字段标识");
      if (keys.has(f.key)) errors.push(`字段标识 "${f.key}" 重复`);
      keys.add(f.key);
      if (!f.label || !f.label.trim()) warnings.push(`字段标识 "${f.key}" 缺少显示名称`);
    }
  }

  return { passed: errors.length === 0, errors, warnings };
}

export function FinanceFormsPage() {
  const [items, setItems] = useState<ManagedFormVersion[]>([]);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<ManagedFormVersion | null>(null);
  const [fields, setFields] = useState<ManagedFormField[]>([
    { key: "", label: "", type: "text", required: true },
  ]);
  const [selectedItem, setSelectedItem] = useState<ManagedFormVersion | null>(null);
  const [showDetail, setShowDetail] = useState(false);
  const [submitDialog, setSubmitDialog] = useState<ManagedFormVersion | null>(null);
  const [preCheck, setPreCheck] = useState<PreCheckResult | null>(null);

  function reload() {
    setError("");
    listManagedForms("finance")
      .then((result) => setItems(result.items))
      .catch((cause: unknown) => setError(cause instanceof Error ? cause.message : "加载失败"));
  }

  useEffect(reload, []);

  function openCreate() {
    setEditing(null);
    setFields([{ key: "", label: "", type: "text", required: true }]);
    setCreating(true);
  }

  function openEdit(item: ManagedFormVersion) {
    setEditing(item);
    setFields(
      item.schema_json.fields?.length
        ? item.schema_json.fields
        : [{ key: "", label: "", type: "text", required: true }],
    );
    setCreating(true);
  }

  function openDetail(item: ManagedFormVersion) {
    setSelectedItem(item);
    setShowDetail(true);
  }

  function updateField(index: number, patch: Partial<ManagedFormField>) {
    setFields((current) =>
      current.map((field, i) => (i === index ? { ...field, ...patch } : field)),
    );
  }

  function addField() {
    setFields((current) => [
      ...current,
      { key: "", label: "", type: "text", required: true },
    ]);
  }

  function removeField(index: number) {
    setFields((current) => current.filter((_, i) => i !== index));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setError("");
    try {
      const saved = editing
        ? await updateManagedForm(editing.version_id, editing.revision, { fields })
        : await createManagedForm({
            name: String(data.get("name") ?? "").trim(),
            form_key: String(data.get("form_key") ?? "").trim().toUpperCase(),
            owner_role: "WORKER",
            schema_json: { fields },
          });
      setItems((current) =>
        editing
          ? current.map((item) => (item.version_id === saved.version_id ? saved : item))
          : [saved, ...current],
      );
      setCreating(false);
      setEditing(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "保存失败");
    }
  }

  async function submitForApproval(item: ManagedFormVersion) {
    const pc = runPreflight(item);
    setPreCheck(pc);
    if (!pc.passed) {
      setError("预检未通过，请修复错误后再提交审批");
      return;
    }
    setSubmitDialog(item);
  }

  async function confirmSubmit(_reason: string) {
    if (!submitDialog) return;
    try {
      const updated = await submitManagedFormApproval(submitDialog.version_id);
      setItems((current) =>
        current.map((v) => (v.version_id === updated.version_id ? updated : v)),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "提交失败");
    } finally {
      setSubmitDialog(null);
      setPreCheck(null);
    }
  }

  async function cloneAsDraft(item: ManagedFormVersion) {
    try {
      const cloned = await createManagedForm({
        name: `${item.name}（副本）`,
        form_key: `${item.form_key}_COPY_${Date.now()}`,
        owner_role: "WORKER",
        schema_json: { fields: item.schema_json.fields ?? [] },
      });
      setItems((current) => [cloned, ...current]);
      openEdit(cloned);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "复制失败");
    }
  }

  function renderActions(item: ManagedFormVersion) {
    const actions = allowedActions(item.status);
    return (
      <div className="finance-form-actions-cell">
        {actions.includes("view") && (
          <button type="button" onClick={() => openDetail(item)}>
            查看
          </button>
        )}
        {(actions.includes("edit")) && (
          <button type="button" className="primary" onClick={() => openEdit(item)}>
            编辑
          </button>
        )}
        {actions.includes("preflight") && (
          <button type="button" onClick={() => {
            const pc = runPreflight(item);
            setPreCheck(pc);
            if (pc.passed) setError("");
            else setError("预检未通过");
          }}>
            预检
          </button>
        )}
        {actions.includes("submit") && (
          <button
            type="button"
            className="primary"
            onClick={() => submitForApproval(item)}
          >
            提交审批
          </button>
        )}
        {actions.includes("clone") && (
          <button type="button" onClick={() => cloneAsDraft(item)}>
            复制为新草稿
          </button>
        )}
        {actions.includes("view_reason") && item.review_comment && (
          <span
            style={{ color: "#9d2424", fontSize: 12, cursor: "pointer" }}
            title={item.review_comment}
          >
            查看退回原因
          </span>
        )}
        {actions.includes("delete") && (
          <button type="button" className="danger">
            删除
          </button>
        )}
      </div>
    );
  }

  return (
    <section className="finance-forms-page" data-testid="finance-forms-page">
      <PageHeader title="电子表单设计" subtitle="以字段卡片创建草稿，审核通过后由管理员按工厂启用。" />

      {error && <ErrorAlert message={error} onRetry={reload} />}

      {/* Pre-check result banner */}
      {preCheck && (
        <div
          className={`workflow-precheck-banner workflow-precheck-banner--${preCheck.passed ? "pass" : "fail"}`}
        >
          <strong>预检{preCheck.passed ? "通过" : "未通过"}</strong>
          {preCheck.errors.length > 0 && (
            <ul>
              {preCheck.errors.map((err, i) => (
                <li key={`e-${i}`}>{err}</li>
              ))}
            </ul>
          )}
          {preCheck.warnings.length > 0 && (
            <ul>
              {preCheck.warnings.map((w, i) => (
                <li key={`w-${i}`}>{w}</li>
              ))}
            </ul>
          )}
          <button
            type="button"
            style={{ justifySelf: "start", padding: "4px 10px", fontSize: 12, border: "1px solid currentColor", borderRadius: 4, background: "transparent", cursor: "pointer", color: "inherit" }}
            onClick={() => setPreCheck(null)}
          >
            关闭
          </button>
        </div>
      )}

      {/* Toolbar */}
      <div className="finance-forms-toolbar">
        <span style={{ color: "#596579", fontSize: 13 }}>
          共 {items.length} 个表单版本
        </span>
        <button type="button" className="primary" onClick={openCreate}>
          新建电子表单
        </button>
      </div>

      {/* Create / Edit form */}
      {creating && (
        <div className="dialog-overlay" role="dialog" aria-modal="true" aria-label="表单编辑器" data-testid="finance-form-editor">
          <div className="dialog-content" style={{ width: "min(640px, 90vw)", maxHeight: "85vh", overflowY: "auto" }}>
            <h2>{editing ? `编辑 ${editing.name}` : "新建表单草稿"}</h2>
            <form className="finance-form-editor-section" onSubmit={save}>
              <label style={{ display: "grid", gap: 4, fontSize: 13, color: "#42566f" }}>
                表单名称
                <input
                  name="name"
                  aria-label="表单名称"
                  defaultValue={editing?.name}
                  disabled={Boolean(editing)}
                  required
                  style={{ padding: "8px 10px", border: "1px solid #b9c6d5", borderRadius: 6, font: "inherit", fontSize: 13 }}
                />
              </label>
              <label style={{ display: "grid", gap: 4, fontSize: 13, color: "#42566f" }}>
                表单标识
                <input
                  name="form_key"
                  aria-label="表单标识"
                  defaultValue={editing?.form_key}
                  disabled={Boolean(editing)}
                  required
                  style={{ padding: "8px 10px", border: "1px solid #b9c6d5", borderRadius: 6, font: "inherit", fontSize: 13 }}
                />
              </label>

              {/* Field list */}
              <div style={{ display: "grid", gap: 8 }}>
                <h3 style={{ margin: 0, fontSize: 14, color: "#42566f" }}>表单字段 ({fields.length})</h3>
                {fields.length > 0 && (
                  <table className="finance-form-field-table">
                    <thead>
                      <tr>
                        <th>序号</th>
                        <th>字段标识</th>
                        <th>显示名称</th>
                        <th>类型</th>
                        <th>必填</th>
                        <th>操作</th>
                      </tr>
                    </thead>
                    <tbody>
                      {fields.map((field, index) => (
                        <tr key={index}>
                          <td>{index + 1}</td>
                          <td>
                            <input
                              aria-label="字段标识"
                              value={field.key}
                              onChange={(e) => updateField(index, { key: e.target.value })}
                              style={{ width: "100%", padding: "4px 6px", border: "1px solid #e7ecf2", borderRadius: 4, font: "inherit", fontSize: 12 }}
                              required
                            />
                          </td>
                          <td>
                            <input
                              aria-label="字段名称"
                              value={field.label}
                              onChange={(e) => updateField(index, { label: e.target.value })}
                              style={{ width: "100%", padding: "4px 6px", border: "1px solid #e7ecf2", borderRadius: 4, font: "inherit", fontSize: 12 }}
                              required
                            />
                          </td>
                          <td>
                            <select
                              aria-label="字段类型"
                              value={field.type}
                              onChange={(e) => updateField(index, { type: e.target.value })}
                              style={{ padding: "4px 6px", border: "1px solid #e7ecf2", borderRadius: 4, font: "inherit", fontSize: 12 }}
                            >
                              <option value="text">文本</option>
                              <option value="number">数字</option>
                              <option value="date">日期</option>
                            </select>
                          </td>
                          <td style={{ textAlign: "center" }}>
                            <input
                              type="checkbox"
                              checked={field.required !== false}
                              onChange={(e) => updateField(index, { required: e.target.checked })}
                              aria-label="必填"
                            />
                          </td>
                          <td>
                            {fields.length > 1 && (
                              <button
                                type="button"
                                onClick={() => removeField(index)}
                                style={{ padding: "2px 8px", border: "1px solid #e7b4b4", borderRadius: 4, background: "#fff", color: "#9d2424", fontSize: 12, cursor: "pointer" }}
                              >
                                删除
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <button
                  type="button"
                  onClick={addField}
                  style={{ justifySelf: "start", padding: "6px 14px", border: "1px dashed #b9c6d5", borderRadius: 6, background: "#fff", font: "inherit", fontSize: 12, cursor: "pointer" }}
                >
                  + 添加字段
                </button>
              </div>

              <div className="dialog-actions">
                <button type="button" className="dialog-btn-cancel" onClick={() => { setCreating(false); setEditing(null); }}>
                  取消
                </button>
                <button type="submit" className="dialog-btn-confirm" style={{ background: "#155eef" }}>
                  保存草稿
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Form list as table */}
      {items.length === 0 ? (
        <EmptyState message="暂无电子表单版本，点击上方按钮创建。" />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="finance-form-list-table">
            <thead>
              <tr>
                <th>表单名称</th>
                <th>版本</th>
                <th>状态</th>
                <th>适用范围</th>
                <th>最近修改</th>
                <th>审批状态</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.version_id}>
                  <td className="finance-form-name-cell">{item.name}</td>
                  <td>V{item.version}</td>
                  <td>
                    <StatusBadge status={item.status} />
                  </td>
                  <td className="finance-form-scope-cell">
                    {item.activation_status === "ACTIVE"
                      ? item.plant_id || "已启用"
                      : item.activation_status === "DISABLED"
                        ? "已停用"
                        : item.owner_role === "WORKER"
                          ? "全员工"
                          : item.owner_role}
                  </td>
                  <td style={{ fontSize: 12, color: "#596579" }}>{formatTime(item.created_at)}</td>
                  <td>
                    {item.status === "REJECTED" && item.review_comment ? (
                      <span style={{ color: "#9d2424", fontSize: 12 }} title={item.review_comment}>
                        已退回
                      </span>
                    ) : item.status === "APPROVED" ? (
                      <span style={{ color: "#1a6b3c", fontSize: 12 }}>已批准</span>
                    ) : (
                      <span style={{ color: "#8593a8", fontSize: 12 }}>—</span>
                    )}
                  </td>
                  <td>{renderActions(item)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail drawer */}
      {showDetail && selectedItem && (
        <div className="finance-drawer-overlay" onClick={() => setShowDetail(false)}>
          <div className="finance-drawer-content" onClick={(e) => e.stopPropagation()}>
            <div className="finance-drawer-header">
              <h2>{selectedItem.name}</h2>
              <button className="finance-drawer-close" onClick={() => setShowDetail(false)}>
                x
              </button>
            </div>
            <div className="finance-drawer-body">
              <div className="finance-detail-section">
                <h3>基本信息</h3>
                <dl className="finance-detail-kv">
                  <dt>表单标识</dt><dd>{selectedItem.form_key}</dd>
                  <dt>版本</dt><dd>V{selectedItem.version}</dd>
                  <dt>状态</dt><dd><StatusBadge status={selectedItem.status} /></dd>
                  <dt>适用范围</dt><dd>{selectedItem.owner_role}</dd>
                  <dt>创建时间</dt><dd>{formatTime(selectedItem.created_at)}</dd>
                  <dt>审批意见</dt><dd>{selectedItem.review_comment || "—"}</dd>
                  <dt>内容哈希</dt><dd style={{ fontSize: 11, fontFamily: "monospace" }}>{selectedItem.content_hash?.slice(0, 20) || "—"}</dd>
                </dl>
              </div>

              <div className="finance-detail-section" style={{ marginTop: 16 }}>
                <h3>字段列表 ({(selectedItem.schema_json.fields ?? []).length} 个)</h3>
                {(selectedItem.schema_json.fields ?? []).length === 0 ? (
                  <p style={{ color: "#596579", fontSize: 13 }}>暂无字段</p>
                ) : (
                  <table className="finance-form-field-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>字段标识</th>
                        <th>显示名称</th>
                        <th>类型</th>
                        <th>必填</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(selectedItem.schema_json.fields ?? []).map((f, i) => (
                        <tr key={i}>
                          <td>{i + 1}</td>
                          <td style={{ fontFamily: "monospace", fontSize: 12 }}>{f.key}</td>
                          <td>{f.label}</td>
                          <td>{f.type}</td>
                          <td style={{ textAlign: "center" }}>{f.required !== false ? "是" : "否"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div style={{ marginTop: 16 }}>
                {renderActions(selectedItem)}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Submit approval dialog */}
      <ReasonConfirmDialog
        open={submitDialog !== null}
        title={`提交审批：${submitDialog?.name ?? ""}`}
        action="APPROVE"
        preCheck={submitDialog ? runPreflight(submitDialog) : undefined}
        onConfirm={(reason) => { void confirmSubmit(reason); }}
        onCancel={() => { setSubmitDialog(null); setPreCheck(null); }}
      />
    </section>
  );
}
