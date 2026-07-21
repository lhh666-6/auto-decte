import { describe, expect, it } from "vitest";

import type { FormFieldDef } from "../types";
import { validateForm } from "./validation";

function field(field_name: string, overrides: Partial<FormFieldDef> = {}): FormFieldDef {
  return {
    field_name,
    field_type: "MANUAL_SHORT_TEXT",
    label: field_name,
    strategy: "DEFAULT_EDITABLE",
    source: "USER",
    required: false,
    preset_options: null,
    default_value: null,
    editable: true,
    input_type: "text",
    ...overrides,
  };
}

describe("validateForm", () => {
  it("returns stable required-field errors", () => {
    const errors = validateForm([
      field("quantity", { label: "数量", strategy: "MANUAL_REQUIRED", required: true }),
    ], {});

    expect(errors).toEqual([{ field: "quantity", message: "请填写数量" }]);
  });

  it("does not validate a conditionally hidden field", () => {
    const errors = validateForm([
      field("exception_note", { label: "异常说明", strategy: "CONDITIONAL_INPUT", required: true }),
    ], { result: "NORMAL" });

    expect(errors).toEqual([]);
  });

  it("validates a conditionally visible required field", () => {
    const errors = validateForm([
      field("exception_note", { label: "异常说明", strategy: "CONDITIONAL_INPUT", required: true }),
    ], { result: "EXCEPTION" });

    expect(errors).toEqual([{ field: "exception_note", message: "请填写异常说明" }]);
  });
});
