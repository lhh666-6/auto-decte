import type {
  FillPolicy,
  PaperEntryMode,
  RecognitionMode,
  TemplateField,
  TemplatePage,
} from "@form-detection/api-client";
import { useEffect, useState } from "react";

import { withDataType, withPaperEntryMode, withRecognitionMode } from "./template-studio-model";

type Props = {
  field: TemplateField | null;
  page: TemplatePage;
  editable: boolean;
  onSave: (field: TemplateField) => Promise<void>;
  onDelete: (fieldKey: string) => Promise<void>;
};

const COORDINATES = ["x", "y", "width", "height"] as const;

export function FieldInspector({ field, page, editable, onSave, onDelete }: Props) {
  const [draft, setDraft] = useState<TemplateField | null>(field);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    setDraft(field === null ? null : structuredClone(field));
  }, [field]);

  if (draft === null) {
    return (
      <aside className="studio-card field-inspector empty-inspector">
        <span className="eyebrow">字段属性</span>
        <h2>尚未选择字段</h2>
        <p className="muted">在画布或左侧图层中选择字段，再编辑填写、识别、校验和导出规则。</p>
      </aside>
    );
  }

  async function save() {
    if (draft === null) return;
    setSaving(true);
    try {
      await onSave(draft);
    } catch {
      // Parent keeps the visible business error and this draft remains available for retry.
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
      // Parent owns the visible API error and keeps the selection intact.
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
        <fieldset>
          <legend>常用设置</legend>
          <label>显示名<input value={draft.display_name} disabled={disabled} onChange={(event) => setDraft({ ...draft, display_name: event.target.value })} /></label>
          <label>数据类型<select value={draft.data_type} disabled={disabled} onChange={(event) => setDraft(withDataType(draft, event.target.value))}><option value="text">文本</option><option value="integer">整数</option><option value="decimal">小数</option><option value="boolean">是/否</option></select></label>
          <label className="checkbox-label"><input type="checkbox" checked={draft.rules.required} disabled={disabled} onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, required: event.target.checked } })} />必填字段</label>
        </fieldset>

        <fieldset>
          <legend>填写与识别</legend>
          <label>纸面填写方式<select value={draft.paper_entry_mode} disabled={disabled} onChange={(event) => setDraft(withPaperEntryMode(draft, event.target.value as PaperEntryMode))}><option value="HANDWRITTEN_TEXT">手写文本</option><option value="DIGIT_BOXES">数字格</option><option value="CHECKBOX">勾选框</option><option value="SIGNATURE">签名</option><option value="PREPRINTED">预印内容</option><option value="NONE">不在纸面填写</option></select></label>
          <label>识别方式<select value={draft.recognition_mode} disabled={disabled} onChange={(event) => setDraft(withRecognitionMode(draft, event.target.value as RecognitionMode))}><option value="NONE">不自动识别</option><option value="HANDWRITING_OCR">手写识别</option><option value="DIGIT_OCR">数字格识别</option><option value="PRINTED_OCR">印刷体识别</option><option value="OMR">勾选识别</option><option value="QR">二维码</option><option value="CALCULATED">计算字段</option></select></label>
          <label>填充策略<select value={draft.fill_policy} disabled={disabled || ["NONE", "CALCULATED"].includes(draft.recognition_mode)} onChange={(event) => setDraft(changeFillPolicy(draft, event.target.value as FillPolicy))}><option value="MANUAL_ONLY">仅人工填写</option><option value="SUGGEST_ONLY">只给建议</option><option value="PREFILL_WHEN_CONFIDENT">达到阈值时预填</option><option value="CALCULATED">自动计算</option></select></label>
          <label>置信阈值<input type="number" min="0" max="1" step="0.01" value={draft.confidence_threshold ?? ""} disabled={disabled || draft.fill_policy !== "PREFILL_WHEN_CONFIDENT"} onChange={(event) => setDraft({ ...draft, confidence_threshold: optionalNumber(event.target.value), minimum_prefill_confidence: optionalNumber(event.target.value) ?? 1 })} /></label>
          <label className="checkbox-label"><input type="checkbox" checked={draft.requires_manual_confirmation} disabled={disabled} onChange={(event) => setDraft({ ...draft, requires_manual_confirmation: event.target.checked })} />必须人工确认</label>
          {draft.recognition_mode === "CALCULATED" && <label>计算表达式<input value={draft.calculation_expression ?? ""} disabled={disabled} onChange={(event) => setDraft({ ...draft, calculation_expression: event.target.value || null })} /></label>}
          {draft.paper_entry_mode === "DIGIT_BOXES" && <label>数字格位数<input type="number" min="1" max="24" step="1" value={draft.digit_count ?? 6} disabled={disabled} onChange={(event) => setDraft({ ...draft, digit_count: Number(event.target.value) })} /></label>}
          {draft.paper_entry_mode === "CHECKBOX" && <>
            <label>固定选项（逗号分隔）<input value={draft.choice_options.join(",")} disabled={disabled} onChange={(event) => setDraft({ ...draft, choice_group: draft.field_key, choice_options: splitOptions(event.target.value) })} /></label>
            <label>最多选择项数<input type="number" min="1" max={Math.max(1, draft.choice_options.length)} step="1" value={draft.max_selections ?? 1} disabled={disabled} onChange={(event) => setDraft({ ...draft, max_selections: Number(event.target.value) })} /></label>
          </>}
          {draft.paper_entry_mode === "NONE" && draft.recognition_mode !== "CALCULATED" && <label>系统带入来源字段<input value={draft.derived_from_field_key ?? ""} disabled={disabled} placeholder="例如：worker_number" onChange={(event) => setDraft({ ...draft, derived_from_field_key: event.target.value.trim() || null })} /></label>}
          {draft.paper_entry_mode === "HANDWRITTEN_TEXT" && <label>条件必填规则<input value={draft.conditional_required_on ?? ""} disabled={disabled} placeholder="例如：quality_result!=合格" onChange={(event) => setDraft({ ...draft, conditional_required_on: event.target.value.trim() || null })} /></label>}
          {draft.paper_entry_mode === "SIGNATURE" && <label>签字角色<select value={draft.signature_role ?? "worker"} disabled={disabled} onChange={(event) => setDraft({ ...draft, signature_role: event.target.value })}><option value="worker">员工</option><option value="team_lead">班组长</option><option value="quality">质检</option><option value="handover">交接人员</option><option value="supervisor">主管</option></select></label>}
        </fieldset>

        <fieldset>
          <legend>校验规则</legend>
          <div className="coordinate-grid">
            <label>最小值<input type="number" step="any" value={draft.rules.minimum_value ?? ""} disabled={disabled || !["integer", "decimal"].includes(draft.data_type)} onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, minimum_value: optionalNumber(event.target.value) } })} /></label>
            <label>最大值<input type="number" step="any" value={draft.rules.maximum_value ?? ""} disabled={disabled || !["integer", "decimal"].includes(draft.data_type)} onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, maximum_value: optionalNumber(event.target.value) } })} /></label>
          </div>
          <label>允许值（逗号分隔）<input value={draft.rules.allowed_values.join(",")} disabled={disabled} onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, allowed_values: event.target.value.split(",").map((item) => item.trim()).filter(Boolean) } })} /></label>
          <label>基础数据源<input value={draft.rules.master_data_source ?? ""} disabled={disabled} placeholder="可留空" onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, master_data_source: event.target.value.trim() || null } })} /></label>
          <label className="checkbox-label"><input type="checkbox" checked={draft.rules.allow_exception_reason} disabled={disabled} onChange={(event) => setDraft({ ...draft, rules: { ...draft.rules, allow_exception_reason: event.target.checked } })} />允许填写异常说明</label>
        </fieldset>

        <fieldset>
          <legend>Excel 导出</legend>
          <label>工作簿<input value={draft.export_target.workbook} disabled={disabled} onChange={(event) => setDraft({ ...draft, export_target: { ...draft.export_target, workbook: event.target.value } })} /></label>
          <label>工作表<input value={draft.export_target.worksheet} disabled={disabled} onChange={(event) => setDraft({ ...draft, export_target: { ...draft.export_target, worksheet: event.target.value } })} /></label>
          <label>业务列<input value={draft.export_target.business_column} disabled={disabled} onChange={(event) => setDraft({ ...draft, export_target: { ...draft.export_target, business_column: event.target.value } })} /></label>
        </fieldset>

        <details className="advanced-field-settings">
          <summary>高级设置</summary>
          <label>字段键<input value={draft.field_key} readOnly aria-readonly="true" /></label>
          <div className="coordinate-grid millimeter-coordinates">
            {COORDINATES.map((name) => <label key={name}>{coordinateLabel(name)}（mm）<input type="number" min="0" step="1" value={toMillimeters(draft, page, name)} disabled={disabled} onChange={(event) => setDraft(fromMillimeters(draft, page, name, Number(event.target.value)))} /></label>)}
          </div>
        </details>

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

function splitOptions(value: string): string[] {
  return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}

function changeFillPolicy(field: TemplateField, policy: FillPolicy): TemplateField {
  return {
    ...field,
    fill_policy: policy,
    confidence_threshold: policy === "PREFILL_WHEN_CONFIDENT" ? (field.confidence_threshold ?? 0.95) : null,
  };
}

function coordinateLabel(name: typeof COORDINATES[number]): string {
  return { x: "左", y: "上", width: "宽", height: "高" }[name];
}

function toMillimeters(field: TemplateField, page: TemplatePage, name: typeof COORDINATES[number]): number {
  const extent = name === "x" || name === "width" ? page.width_mm : page.height_mm;
  return Math.round(field.region[name] * extent);
}

function fromMillimeters(field: TemplateField, page: TemplatePage, name: typeof COORDINATES[number], value: number): TemplateField {
  const extent = name === "x" || name === "width" ? page.width_mm : page.height_mm;
  return { ...field, region: { ...field.region, [name]: value / extent } };
}
