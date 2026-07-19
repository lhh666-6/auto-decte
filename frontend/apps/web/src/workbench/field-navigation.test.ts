import { describe, expect, it } from "vitest";

import type { ReviewField, ReviewFieldRules } from "@form-detection/api-client";

import {
  nextFieldId,
  previousFieldId,
  selectFirstIssueFieldId,
  setHoveredFieldId,
  type FieldNavigationState,
} from "./field-navigation";

const BASE_RULES: ReviewFieldRules = {
  required: false,
  minimum_value: null,
  maximum_value: null,
  allowed_values: [],
  master_data_source: null,
  master_data_options: [],
};

function field(
  fieldId: string,
  currentValue: unknown,
  options: {
    confidence?: number;
    rules?: ReviewFieldRules | null;
    requiresManualConfirmation?: boolean;
  } = {},
): ReviewField {
  return {
    field_id: fieldId,
    field_name: fieldId,
    display_name: fieldId,
    data_type: "text",
    recognition_engine: options.confidence === undefined ? "manual" : "ocr",
    paper_entry_mode: "HANDWRITTEN_TEXT",
    recognition_mode: options.confidence === undefined ? "NONE" : "HANDWRITING_OCR",
    fill_policy: options.confidence === undefined ? "MANUAL_ONLY" : "SUGGEST_ONLY",
    requires_manual_confirmation: options.requiresManualConfirmation ?? false,
    rules: options.rules ?? null,
    source_region: {},
    current_value: currentValue,
    current_value_source: null,
    current_record_version: 0,
    candidates: options.confidence === undefined ? [] : [{
      attempt_id: `${fieldId}-attempt`,
      candidate_value: currentValue,
      confidence: options.confidence,
      engine: "test",
      model_version: "1",
      crop_file_id: `${fieldId}-crop`,
    }],
  };
}

describe("selectFirstIssueFieldId", () => {
  it("orders invalid, required, low-confidence, manual-confirmation and normal fields", () => {
    const fields = [
      field("normal", "正常", { confidence: 0.99 }),
      field("manual-confirmation", "候选姓名", {
        confidence: 0.99,
        requiresManualConfirmation: true,
      }),
      field("low-confidence", "候选", { confidence: 0.4 }),
      field("required", "", { rules: { ...BASE_RULES, required: true } }),
      field("invalid", "错误", {
        rules: { ...BASE_RULES, allowed_values: ["正确"] },
      }),
    ];

    expect(selectFirstIssueFieldId(fields, {}, {})).toBe("invalid");
    expect(selectFirstIssueFieldId(fields, { invalid: "正确" }, {})).toBe("required");
    expect(selectFirstIssueFieldId(fields, {
      invalid: "正确",
      required: "已填写",
    }, {})).toBe("low-confidence");
    expect(selectFirstIssueFieldId(fields, {
      invalid: "正确",
      required: "已填写",
      "low-confidence": "人工确认候选",
    }, {})).toBe("manual-confirmation");
    expect(selectFirstIssueFieldId(fields, {
      invalid: "正确",
      required: "已填写",
      "low-confidence": "人工确认候选",
      "manual-confirmation": "人工填写",
    }, {})).toBe("normal");
  });

  it("treats a server rule failure as the highest-priority filling error", () => {
    const fields = [field("first", "正常"), field("server-invalid", "正常")];

    expect(selectFirstIssueFieldId(fields, {}, {
      "server-invalid": "服务端规则拒绝该值",
    })).toBe("server-invalid");
  });

  it("returns the first field without issues and null for an empty field list", () => {
    expect(selectFirstIssueFieldId([
      field("first", "正常"),
      field("second", "正常"),
    ], {}, {})).toBe("first");
    expect(selectFirstIssueFieldId([], {}, {})).toBeNull();
  });
});

describe("field boundary navigation", () => {
  const fields = [field("first", "1"), field("middle", "2"), field("last", "3")];

  it("moves forward without passing the last field", () => {
    expect(nextFieldId(fields, "first")).toBe("middle");
    expect(nextFieldId(fields, "last")).toBe("last");
    expect(nextFieldId(fields, null)).toBe("first");
  });

  it("moves backward without passing the first field", () => {
    expect(previousFieldId(fields, "last")).toBe("middle");
    expect(previousFieldId(fields, "first")).toBe("first");
    expect(previousFieldId(fields, null)).toBe("last");
  });
});

describe("field interaction state", () => {
  it("clears hover without changing the formal selection", () => {
    const state: FieldNavigationState = {
      selectedFieldId: "selected",
      hoveredFieldId: "hovered",
    };

    expect(setHoveredFieldId(state, null)).toEqual({
      selectedFieldId: "selected",
      hoveredFieldId: null,
    });
    expect(state).toEqual({
      selectedFieldId: "selected",
      hoveredFieldId: "hovered",
    });
  });
});
