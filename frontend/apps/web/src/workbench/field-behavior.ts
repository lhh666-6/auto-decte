import type { ReviewField } from "@form-detection/api-client";

const PAPER_ENTRY_LABELS: Readonly<Record<string, string>> = {
  HANDWRITTEN_TEXT: "手写文字",
  DIGIT_BOXES: "逐位数字格",
  CHECKBOX: "勾选方框",
  SIGNATURE: "签字",
  PREPRINTED: "预印内容",
  NONE: "无需填写",
};

const RECOGNITION_LABELS: Readonly<Record<string, string>> = {
  NONE: "不自动识别",
  HANDWRITING_OCR: "手写识别",
  DIGIT_OCR: "数字格识别",
  PRINTED_OCR: "印刷文字识别",
  OMR: "勾选识别",
  QR: "二维码识别",
  CALCULATED: "自动计算",
};

const FILL_POLICY_LABELS: Readonly<Record<string, string>> = {
  MANUAL_ONLY: "完全由工作人员填写",
  SUGGEST_ONLY: "只显示识别建议",
  PREFILL_WHEN_CONFIDENT: "达到条件时预填",
  CALCULATED: "根据规则自动计算",
};

export function fieldUsesAutomaticRecognition(field: ReviewField): boolean {
  if (field.recognition_mode !== null && field.recognition_mode !== undefined) {
    return field.recognition_mode !== "NONE";
  }
  return field.recognition_engine !== "manual";
}

export function fieldBehaviorSummary(field: ReviewField): string {
  const paper = label(PAPER_ENTRY_LABELS, field.paper_entry_mode, "纸面填写方式未配置");
  const recognition = label(
    RECOGNITION_LABELS,
    field.recognition_mode,
    field.recognition_engine === "manual" ? "不自动识别" : "识别方式未配置",
  );
  const fill = label(FILL_POLICY_LABELS, field.fill_policy, "填入方式未配置");
  return `${paper} · ${recognition} · ${fill}`;
}

function label(
  labels: Readonly<Record<string, string>>,
  value: string | null,
  fallback: string,
): string {
  return value ? labels[value] ?? value : fallback;
}
