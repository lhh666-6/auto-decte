import type { TemplateField } from "@form-detection/api-client";
import { useEffect, useState } from "react";

type Props = {
  field: TemplateField | null;
  editable: boolean;
  onSave: (field: TemplateField) => Promise<void>;
  onDelete: (fieldKey: string) => Promise<void>;
};

const COORDINATES = ["x", "y", "width", "height"] as const;

export function FieldInspector({ field, editable, onSave, onDelete }: Props) {
  const [draft, setDraft] = useState<TemplateField | null>(field);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setDraft(field === null ? null : { ...field, region: { ...field.region } });
  }, [field]);

  if (draft === null) {
    return (
      <aside className="studio-card field-inspector empty-inspector">
        <span className="eyebrow">字段属性</span>
        <h2>尚未选择字段</h2>
        <p className="muted">在画布或左侧图层列表中选择字段，然后编辑识别策略与坐标。</p>
      </aside>
    );
  }

  async function save() {
    if (draft === null) return;
    setSaving(true);
    try {
      await onSave(draft);
    } catch {
      // The parent owns the visible API or validation error; keep this local draft for retry.
    } finally {
      setSaving(false);
    }
  }

  async function remove() {
    if (draft === null || !window.confirm(`确定删除字段“${draft.display_name}”吗？`)) return;
    setDeleting(true);
    try {
      await onDelete(draft.field_key);
    } catch {
      // The parent owns the visible API error and keeps the selected field available.
    } finally {
      setDeleting(false);
    }
  }

  const disabled = !editable || saving || deleting;
  return (
    <aside className="studio-card field-inspector">
      <div className="inspector-heading">
        <div><span className="eyebrow">字段属性</span><h2>{draft.display_name}</h2></div>
        <span className={`status-pill ${editable ? "warning" : "success"}`}>{editable ? "可编辑" : "只读"}</span>
      </div>
      <form onSubmit={(event) => { event.preventDefault(); void save(); }}>
        <label>字段键<input value={draft.field_key} readOnly aria-readonly="true" /></label>
        <label>显示名<input value={draft.display_name} disabled={disabled} onChange={(event) => setDraft({ ...draft, display_name: event.target.value })} /></label>
        <label>数据类型<select value={draft.data_type} disabled={disabled} onChange={(event) => setDraft({ ...draft, data_type: event.target.value })}><option value="text">文本</option><option value="integer">整数</option><option value="decimal">小数</option><option value="boolean">布尔值</option></select></label>
        <label>输入类型<select value={draft.input_type} disabled={disabled} onChange={(event) => setDraft({ ...draft, input_type: event.target.value })}><option value="text_box">文本框</option><option value="digit_boxes">数字格</option><option value="checkbox">勾选框</option></select></label>
        <label>识别引擎<select value={draft.recognition_engine} disabled={disabled} onChange={(event) => setDraft({ ...draft, recognition_engine: event.target.value })}><option value="manual">人工填写</option><option value="digit_template">数字格识别</option><option value="omr">OMR 勾选</option></select></label>
        <label>自动预填阈值<input type="number" min="0" max="1" step="0.01" value={draft.minimum_prefill_confidence} disabled={disabled} onChange={(event) => setDraft({ ...draft, minimum_prefill_confidence: Number(event.target.value) })} /></label>
        <label className="checkbox-label"><input type="checkbox" checked={draft.rules.required} disabled={disabled} onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, required: event.target.checked } })} />必填字段</label>
        <div className="coordinate-grid">
          <label>最小值<input type="number" step="any" value={draft.rules.minimum_value ?? ""} disabled={disabled || !["integer", "decimal"].includes(draft.data_type)} onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, minimum_value: optionalNumber(event.target.value) } })} /></label>
          <label>最大值<input type="number" step="any" value={draft.rules.maximum_value ?? ""} disabled={disabled || !["integer", "decimal"].includes(draft.data_type)} onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, maximum_value: optionalNumber(event.target.value) } })} /></label>
        </div>
        <label>允许值（逗号分隔）<input value={draft.rules.allowed_values.join(",")} disabled={disabled} onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, allowed_values: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) } })} /></label>
        <label>主数据源<input value={draft.rules.master_data_source ?? ""} disabled={disabled} placeholder="可留空" onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, master_data_source: event.target.value.trim() || null } })} /></label>
        <label className="checkbox-label"><input type="checkbox" checked={draft.rules.allow_exception_reason} disabled={disabled} onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, allow_exception_reason: event.target.checked } })} />允许填写异常说明</label>
        <label>导出工作簿<input value={draft.export_target.workbook} disabled={disabled} onChange={(event) => setDraft({ ...draft, export_target: { ...draft.export_target, workbook: event.target.value } })} /></label>
        <label>导出工作表<input value={draft.export_target.worksheet} disabled={disabled} onChange={(event) => setDraft({ ...draft, export_target: { ...draft.export_target, worksheet: event.target.value } })} /></label>
        <label>业务列键<input value={draft.export_target.business_column} disabled={disabled} onChange={(event) => setDraft({ ...draft, export_target: { ...draft.export_target, business_column: event.target.value } })} /></label>
        <div className="coordinate-grid">
          {COORDINATES.map((name) => <label key={name}>{name}<input type="number" min="0" max="1" step="0.005" value={draft.region[name]} disabled={disabled} onChange={(event) => setDraft({ ...draft, region: { ...draft.region, [name]: Number(event.target.value) } })} /></label>)}
        </div>
        <div className="inspector-actions">
          <button type="submit" className="button button-primary" disabled={disabled}>{saving ? "正在保存…" : "保存字段"}</button>
          <button type="button" className="button button-danger" disabled={disabled} onClick={() => void remove()}>{deleting ? "正在删除…" : "删除字段"}</button>
        </div>
      </form>
    </aside>
  );
}

function optionalNumber(value: string): number | null {
  return value.trim() === "" ? null : Number(value);
}
