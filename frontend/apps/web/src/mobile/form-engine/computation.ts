import type { FormFieldDef } from "../types";
import { classifyStrategy, type ComputeMap, type ComputeRule } from "./types";

const BUILTIN_COMPUTE: ComputeMap = new Map([
  ["total_piece_count", (values) =>
    (Number(values.pieces_per_block) || 0) * (Number(values.block_count) || 0)],
]);

export function buildComputeMap(extra: ComputeRule[] = []): ComputeMap {
  const result: ComputeMap = new Map(BUILTIN_COMPUTE);
  for (const rule of extra) result.set(rule.fieldName, rule.compute);
  return result;
}

export function computePreview(
  fieldName: string,
  values: Record<string, unknown>,
  computeMap: ComputeMap,
): number | string {
  return computeMap.get(fieldName)?.(values) ?? "—";
}

export function buildSubmissionValues(
  fields: FormFieldDef[],
  values: Record<string, unknown>,
  computeMap: ComputeMap,
): Record<string, unknown> {
  return Object.fromEntries(fields.map((field) => {
    if (classifyStrategy(field.strategy) === "computed") {
      return [field.field_name, computeMap.get(field.field_name)?.(values) ?? values[field.field_name] ?? ""];
    }
    return [field.field_name, values[field.field_name] ?? field.default_value ?? ""];
  }));
}
