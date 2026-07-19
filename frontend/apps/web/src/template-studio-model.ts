import type {
  PaperEntryMode,
  RecognitionMode,
  TemplateField,
  TemplatePage,
  TemplateRect,
} from "../../../packages/api-client/src/templates_ds";

export const QR_SAFE_ZONE: TemplateRect = { x: 0.78, y: 0.02, width: 0.16, height: 0.12 };
export const SHEET_CODE_SAFE_ZONE: TemplateRect = { x: 0.62, y: 0.02, width: 0.14, height: 0.12 };
export const PROTECTED_PLACEMENT_MESSAGE = "该位置属于二维码、实例码、定位标记或打印安全区，不能放置字段。";

const PAGE_EDGE = 0.025;
const CORNER_MARKER = 0.07;

export const PROTECTED_ZONES: readonly TemplateRect[] = [
  QR_SAFE_ZONE,
  SHEET_CODE_SAFE_ZONE,
  { x: 0, y: 0, width: 1, height: PAGE_EDGE },
  { x: 0, y: 1 - PAGE_EDGE, width: 1, height: PAGE_EDGE },
  { x: 0, y: 0, width: PAGE_EDGE, height: 1 },
  { x: 1 - PAGE_EDGE, y: 0, width: PAGE_EDGE, height: 1 },
  { x: 0, y: 0, width: CORNER_MARKER, height: CORNER_MARKER },
  { x: 1 - CORNER_MARKER, y: 0, width: CORNER_MARKER, height: CORNER_MARKER },
  { x: 0, y: 1 - CORNER_MARKER, width: CORNER_MARKER, height: CORNER_MARKER },
  {
    x: 1 - CORNER_MARKER,
    y: 1 - CORNER_MARKER,
    width: CORNER_MARKER,
    height: CORNER_MARKER,
  },
];

type ProtectedRegion = TemplateRect | readonly TemplateRect[];

export function isProtectedOverlap(
  rect: TemplateRect,
  protectedRegion: ProtectedRegion = PROTECTED_ZONES,
): boolean {
  const candidate = normalizeRect(rect);
  const zones = Array.isArray(protectedRegion) ? protectedRegion : [protectedRegion];
  return zones.some((item) => {
    const zone = normalizeRect(item);
    return candidate.x < zone.x + zone.width
      && candidate.x + candidate.width > zone.x
      && candidate.y < zone.y + zone.height
      && candidate.y + candidate.height > zone.y;
  });
}

export function moveRect(
  rect: TemplateRect,
  deltaX: number,
  deltaY: number,
  protectedRegion: ProtectedRegion = PROTECTED_ZONES,
): TemplateRect {
  const current = normalizeRect(rect);
  const candidate = {
    ...current,
    x: clamp(current.x + deltaX, 0, 1 - current.width),
    y: clamp(current.y + deltaY, 0, 1 - current.height),
  };
  return isProtectedOverlap(candidate, protectedRegion) ? rect : candidate;
}

export function resizeRect(
  rect: TemplateRect,
  width: number,
  height: number,
  protectedRegion: ProtectedRegion = PROTECTED_ZONES,
): TemplateRect {
  const current = normalizeRect(rect);
  const candidate = {
    ...current,
    width: clamp(width, 0, 1 - current.x),
    height: clamp(height, 0, 1 - current.y),
  };
  return isProtectedOverlap(candidate, protectedRegion) ? rect : candidate;
}

export function canEdit(status: string): boolean {
  return status === "DRAFT" || status === "PREFLIGHT_FAILED" || status === "READY_TO_PUBLISH";
}

export type Alignment = "left" | "horizontal-center" | "right" | "top" | "vertical-center" | "bottom";

export function snapRectToMillimeters(
  rect: TemplateRect,
  page: Pick<TemplatePage, "width_mm" | "height_mm">,
  gridMm = 1,
): TemplateRect {
  if (gridMm <= 0) return normalizeRect(rect);
  const snap = (value: number, extent: number) => Math.round((value * extent) / gridMm) * gridMm / extent;
  return normalizeRect({
    x: snap(rect.x, page.width_mm),
    y: snap(rect.y, page.height_mm),
    width: snap(rect.width, page.width_mm),
    height: snap(rect.height, page.height_mm),
  });
}

export function rectInMillimeters(
  rect: TemplateRect,
  page: Pick<TemplatePage, "width_mm" | "height_mm">,
): TemplateRect {
  return {
    x: round(rect.x * page.width_mm),
    y: round(rect.y * page.height_mm),
    width: round(rect.width * page.width_mm),
    height: round(rect.height * page.height_mm),
  };
}

export function alignRect(
  rect: TemplateRect,
  alignment: Alignment,
  protectedRegion: ProtectedRegion = PROTECTED_ZONES,
): TemplateRect {
  const current = normalizeRect(rect);
  const candidate = { ...current };
  if (alignment === "left") candidate.x = PAGE_EDGE;
  if (alignment === "horizontal-center") candidate.x = (1 - current.width) / 2;
  if (alignment === "right") candidate.x = 1 - PAGE_EDGE - current.width;
  if (alignment === "top") candidate.y = PAGE_EDGE;
  if (alignment === "vertical-center") candidate.y = (1 - current.height) / 2;
  if (alignment === "bottom") candidate.y = 1 - PAGE_EDGE - current.height;
  const normalized = normalizeRect(candidate);
  return isProtectedOverlap(normalized, protectedRegion) ? rect : normalized;
}

export function createFieldDraft(existingKeys: readonly string[]): TemplateField {
  let suffix = existingKeys.length + 1;
  while (existingKeys.includes(`field_${suffix}`)) suffix += 1;
  const fieldKey = `field_${suffix}`;
  return {
    field_key: fieldKey,
    display_name: `新字段 ${suffix}`,
    data_type: "text",
    input_type: "text_box",
    recognition_engine: "manual",
    minimum_prefill_confidence: 1,
    paper_entry_mode: "HANDWRITTEN_TEXT",
    recognition_mode: "NONE",
    fill_policy: "MANUAL_ONLY",
    confidence_threshold: null,
    requires_manual_confirmation: true,
    calculation_expression: null,
    digit_count: null,
    choice_group: null,
    choice_options: [],
    max_selections: null,
    derived_from_field_key: null,
    conditional_required_on: null,
    signature_role: null,
    rules: {
      required: false,
      minimum_value: null,
      maximum_value: null,
      allowed_values: [],
      master_data_source: null,
      allow_exception_reason: false,
    },
    export_target: {
      workbook: "records.xlsx",
      worksheet: "records",
      business_column: fieldKey,
    },
    region: { x: 0.1, y: 0.2, width: 0.22, height: 0.05 },
  };
}

export function hasDuplicateFieldKey(fieldKey: string, fields: readonly TemplateField[]): boolean {
  return fields.some((field) => field.field_key.trim() === fieldKey.trim());
}

export function withDataType(field: TemplateField, dataType: string): TemplateField {
  const numeric = dataType === "integer" || dataType === "decimal";
  const updated = {
    ...field,
    data_type: dataType,
    rules: {
      ...field.rules,
      minimum_value: numeric ? field.rules.minimum_value : null,
      maximum_value: numeric ? field.rules.maximum_value : null,
      allowed_values: dataType === "boolean" ? [] : field.rules.allowed_values,
    },
  };
  if (field.recognition_mode === "DIGIT_OCR" && !numeric) return withRecognitionMode(updated, "NONE");
  if (field.recognition_mode === "OMR" && dataType !== "boolean") return withRecognitionMode(updated, "NONE");
  return updated;
}

export function withRecognitionMode(field: TemplateField, recognitionMode: RecognitionMode): TemplateField {
  const legacyEngine = {
    NONE: "manual",
    HANDWRITING_OCR: "handwriting_ocr",
    DIGIT_OCR: "digit_template",
    PRINTED_OCR: "printed_ocr",
    OMR: "omr",
    QR: "qr",
    CALCULATED: "calculated",
  }[recognitionMode];
  if (recognitionMode === "NONE") {
    return {
      ...field,
      recognition_mode: recognitionMode,
      recognition_engine: legacyEngine,
      fill_policy: "MANUAL_ONLY",
      confidence_threshold: null,
      calculation_expression: null,
    };
  }
  if (recognitionMode === "CALCULATED") {
    return {
      ...withPaperEntryMode(field, "NONE"),
      recognition_mode: recognitionMode,
      recognition_engine: legacyEngine,
      fill_policy: "CALCULATED",
      confidence_threshold: null,
      requires_manual_confirmation: false,
      derived_from_field_key: null,
    };
  }
  const compatibility = ({
    HANDWRITING_OCR: { paper_entry_mode: "HANDWRITTEN_TEXT", input_type: "text_box" },
    DIGIT_OCR: { paper_entry_mode: "DIGIT_BOXES", input_type: "digit_boxes" },
    PRINTED_OCR: { paper_entry_mode: "PREPRINTED", input_type: "preprinted" },
    OMR: { paper_entry_mode: "CHECKBOX", input_type: "checkbox" },
    QR: { paper_entry_mode: "PREPRINTED", input_type: "preprinted" },
  } as const)[recognitionMode];
  const controlled = withPaperEntryMode(field, compatibility.paper_entry_mode);
  return {
    ...controlled,
    ...compatibility,
    data_type: recognitionMode === "OMR"
      ? "boolean"
      : recognitionMode === "DIGIT_OCR" && !["integer", "decimal"].includes(field.data_type)
        ? "decimal"
        : field.data_type,
    recognition_mode: recognitionMode,
    recognition_engine: legacyEngine,
    fill_policy: "SUGGEST_ONLY",
    confidence_threshold: null,
    calculation_expression: null,
  };
}

export function withPaperEntryMode(
  field: TemplateField,
  mode: PaperEntryMode,
): TemplateField {
  const inputType = {
    HANDWRITTEN_TEXT: "text_box",
    DIGIT_BOXES: "digit_boxes",
    CHECKBOX: "checkbox",
    SIGNATURE: "signature",
    PREPRINTED: "preprinted",
    NONE: "none",
  }[mode];
  const existingChoices = field.choice_options.length > 0
    ? field.choice_options
    : ["是", "否"];
  return {
    ...field,
    paper_entry_mode: mode,
    input_type: inputType,
    digit_count: mode === "DIGIT_BOXES" ? (field.digit_count ?? 6) : null,
    choice_group: mode === "CHECKBOX" ? (field.choice_group ?? field.field_key) : null,
    choice_options: mode === "CHECKBOX" ? existingChoices : [],
    max_selections: mode === "CHECKBOX" ? (field.max_selections ?? 1) : null,
    derived_from_field_key: mode === "NONE" ? field.derived_from_field_key : null,
    conditional_required_on: mode === "HANDWRITTEN_TEXT" ? field.conditional_required_on : null,
    signature_role: mode === "SIGNATURE" ? (field.signature_role ?? "worker") : null,
  };
}

function normalizeRect(rect: TemplateRect): TemplateRect {
  const x = clamp(rect.x, 0, 1);
  const y = clamp(rect.y, 0, 1);
  return {
    x,
    y,
    width: clamp(rect.width, 0, 1 - x),
    height: clamp(rect.height, 0, 1 - y),
  };
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.round(Math.min(Math.max(value, minimum), maximum) * 1_000_000_000_000) / 1_000_000_000_000;
}

function round(value: number): number {
  return Math.round(value * 1000) / 1000;
}
