import type { FormFieldDef } from "../types";
import { classifyStrategy, type ConditionalMap, type ConditionalRule } from "./types";

export interface FormValidationError {
  field: string;
  message: string;
}

export const BUILTIN_CONDITIONAL_RULES: ConditionalRule[] = [
  { fieldName: "exception_type", dependsOn: "result", showWhen: (value) => value === "EXCEPTION" || value === "异常" },
  { fieldName: "exception_note", dependsOn: "result", showWhen: (value) => value === "EXCEPTION" || value === "异常" },
];

export function buildConditionalMap(extra: ConditionalRule[] = []): ConditionalMap {
  const result: ConditionalMap = new Map();
  for (const rule of BUILTIN_CONDITIONAL_RULES) result.set(rule.fieldName, rule);
  for (const rule of extra) result.set(rule.fieldName, rule);
  return result;
}

export function isFieldVisible(
  field: FormFieldDef,
  values: Record<string, unknown>,
  conditionals: ConditionalMap,
): boolean {
  if (classifyStrategy(field.strategy) === "hidden") return false;
  if (field.strategy !== "CONDITIONAL_INPUT") return true;
  const rule = conditionals.get(field.field_name);
  return !rule || rule.showWhen(values[rule.dependsOn]);
}

function isMissing(value: unknown): boolean {
  return value === null
    || value === undefined
    || value === ""
    || (Array.isArray(value) && value.length === 0);
}

export function validateForm(
  fields: FormFieldDef[],
  values: Record<string, unknown>,
  conditionals: ConditionalMap = buildConditionalMap(),
): FormValidationError[] {
  const errors: FormValidationError[] = [];
  for (const field of fields) {
    const strategy = classifyStrategy(field.strategy);
    if (strategy === "hidden" || !isFieldVisible(field, values, conditionals)) continue;
    if ((strategy === "required" || field.required) && isMissing(values[field.field_name])) {
      errors.push({ field: field.field_name, message: `请填写${field.label}` });
    }
  }
  return errors;
}
