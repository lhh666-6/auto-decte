import type { EvidenceItem, ReviewFieldRules } from "@form-detection/api-client";

export interface ReviewValueField {
  fieldId: string;
  currentValue: unknown;
}

export interface ReviewEvidenceSelection {
  evidence: EvidenceItem | null;
  coordinateSpace: "canonical" | "original" | "none";
}

export function reviewValueNeedsConfirmation(
  value: unknown,
  candidateConfidence: number | undefined,
  manuallyEdited: boolean,
): boolean {
  const blank = value === null || value === undefined ||
    (typeof value === "string" && value.trim() === "");
  if (blank) return true;
  return !manuallyEdited && candidateConfidence !== undefined && candidateConfidence < 0.8;
}

export function reviewValueIssue(
  value: unknown,
  candidateConfidence: number | undefined,
  manuallyEdited: boolean,
  dataType: string | null,
  rules: ReviewFieldRules | null,
): string | null {
  const blank = value === null || value === undefined ||
    (typeof value === "string" && value.trim() === "");
  if (blank) {
    if (rules === null) return "请填写或确认字段值";
    return rules.required ? "必填字段缺失" : null;
  }
  if (rules?.allowed_values.length && !rules.allowed_values.includes(String(value))) {
    return `请选择：${rules.allowed_values.join(" / ")}`;
  }
  if (
    rules?.master_data_source &&
    !rules.master_data_options.some((option) => option.value === String(value))
  ) {
    return "请选择有效的主数据记录";
  }
  if (dataType === "integer" || dataType === "decimal") {
    const text = String(value).trim();
    const numeric = Number(text);
    if (!Number.isFinite(numeric) || (dataType === "integer" && !/^[+-]?\d+$/.test(text))) {
      return dataType === "integer" ? "请输入整数" : "请输入数值";
    }
    if (rules?.minimum_value !== null && rules?.minimum_value !== undefined && numeric < rules.minimum_value) {
      return `数值不能小于 ${rules.minimum_value}`;
    }
    if (rules?.maximum_value !== null && rules?.maximum_value !== undefined && numeric > rules.maximum_value) {
      return `数值不能大于 ${rules.maximum_value}`;
    }
  }
  if (!manuallyEdited && candidateConfidence !== undefined && candidateConfidence < 0.8) {
    return "识别置信度较低，请人工确认";
  }
  return null;
}

export function selectReviewEvidence(
  evidence: readonly EvidenceItem[],
): ReviewEvidenceSelection {
  const corrected = evidence.find((item) => item.type === "CORRECTED_IMAGE");
  if (corrected) return { evidence: corrected, coordinateSpace: "canonical" };

  const original = evidence.find((item) => item.type === "ORIGINAL_IMAGE");
  if (original) return { evidence: original, coordinateSpace: "original" };

  return { evidence: null, coordinateSpace: "none" };
}

export function buildConfirmValues(
  fields: readonly ReviewValueField[],
  edits: Readonly<Record<string, unknown>>,
): Record<string, unknown> {
  return Object.fromEntries(
    fields.map((field) => [
      field.fieldId,
      Object.hasOwn(edits, field.fieldId) ? edits[field.fieldId] : field.currentValue,
    ]),
  );
}
