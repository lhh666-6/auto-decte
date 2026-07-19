import type { ReviewField } from "@form-detection/api-client";

import { reviewValueIssue } from "../review-model";
import { fieldUsesAutomaticRecognition } from "./field-behavior";

export interface FieldNavigationState {
  readonly selectedFieldId: string | null;
  readonly hoveredFieldId: string | null;
}

export function selectFirstIssueFieldId(
  fields: readonly ReviewField[],
  edits: Readonly<Record<string, unknown>>,
  ruleFailures: Readonly<Record<string, string>>,
): string | null {
  if (fields.length === 0) return null;

  let selected = fields[0];
  let selectedPriority = fieldIssuePriority(selected, edits, ruleFailures);
  for (const field of fields.slice(1)) {
    const priority = fieldIssuePriority(field, edits, ruleFailures);
    if (priority < selectedPriority) {
      selected = field;
      selectedPriority = priority;
    }
  }
  return selected.field_id;
}

export function nextFieldId(
  fields: readonly ReviewField[],
  selectedFieldId: string | null,
): string | null {
  if (fields.length === 0) return null;
  const selectedIndex = fields.findIndex((field) => field.field_id === selectedFieldId);
  if (selectedIndex < 0) return fields[0].field_id;
  return fields[Math.min(selectedIndex + 1, fields.length - 1)].field_id;
}

export function previousFieldId(
  fields: readonly ReviewField[],
  selectedFieldId: string | null,
): string | null {
  if (fields.length === 0) return null;
  const selectedIndex = fields.findIndex((field) => field.field_id === selectedFieldId);
  if (selectedIndex < 0) return fields[fields.length - 1].field_id;
  return fields[Math.max(selectedIndex - 1, 0)].field_id;
}

export function setHoveredFieldId(
  state: FieldNavigationState,
  hoveredFieldId: string | null,
): FieldNavigationState {
  return { ...state, hoveredFieldId };
}

function fieldIssuePriority(
  field: ReviewField,
  edits: Readonly<Record<string, unknown>>,
  ruleFailures: Readonly<Record<string, string>>,
): number {
  if (ruleFailures[field.field_id] ?? ruleFailures[field.field_name]) return 0;

  const editedById = Object.hasOwn(edits, field.field_id);
  const editedByName = Object.hasOwn(edits, field.field_name);
  const value = editedById
    ? edits[field.field_id]
    : editedByName
      ? edits[field.field_name]
      : field.current_value;
  const issue = reviewValueIssue(
    value,
    fieldUsesAutomaticRecognition(field) ? field.candidates[0]?.confidence : undefined,
    editedById || editedByName || field.current_value_source === "HUMAN_CONFIRMED",
    field.data_type,
    field.rules,
    field.requires_manual_confirmation,
  );

  if (issue === null) return 4;
  if (issue === "必填字段缺失") return 1;
  if (issue === "识别置信度较低，请人工确认") return 2;
  if (issue === "必须对照字段裁片人工确认") return 3;
  if (issue === "请填写或确认字段值") return 3;
  return 0;
}
