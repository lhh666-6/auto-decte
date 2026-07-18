import { describe, expect, it } from "vitest";

import {
  PROTECTED_ZONES,
  QR_SAFE_ZONE,
  alignRect,
  canEdit,
  createFieldDraft,
  hasDuplicateFieldKey,
  isProtectedOverlap,
  moveRect,
  rectInMillimeters,
  resizeRect,
  snapRectToMillimeters,
  withDataType,
  withRecognitionMode,
} from "./template-studio-model";

describe("template studio canvas model", () => {
  it("moves a field within the printable page", () => {
    expect(moveRect({ x: 0.12, y: 0.22, width: 0.2, height: 0.05 }, 0.03, 0.01, QR_SAFE_ZONE))
      .toEqual({ x: 0.15, y: 0.23, width: 0.2, height: 0.05 });
  });

  it("keeps an already protected rectangle exactly unchanged when moved", () => {
    const original = { x: 0.74, y: 0.10, width: 0.20, height: 0.05 };

    expect(moveRect(original, 0.10, 0, QR_SAFE_ZONE)).toBe(original);
  });

  it("keeps the original rectangle when a move enters the QR safe zone", () => {
    const original = { x: 0.55, y: 0.10, width: 0.2, height: 0.05 };

    expect(moveRect(original, 0.1, 0, QR_SAFE_ZONE)).toBe(original);
    expect(isProtectedOverlap({ x: 0.8, y: 0.02, width: 0.01, height: 0.01 }, QR_SAFE_ZONE)).toBe(true);
  });

  it("resizes within the page and rejects a protected placement", () => {
    expect(resizeRect({ x: 0.6, y: 0.4, width: 0.3, height: 0.2 }, 0.4, 0.7, QR_SAFE_ZONE))
      .toEqual({ x: 0.6, y: 0.4, width: 0.4, height: 0.6 });

    const original = { x: 0.55, y: 0.1, width: 0.2, height: 0.05 };
    expect(resizeRect(original, 0.3, 0.05, QR_SAFE_ZONE)).toBe(original);
  });

  it("protects the instance code, corner markers, and printable page edge", () => {
    const nearInstanceCode = { x: 0.50, y: 0.05, width: 0.10, height: 0.04 };
    const nearTopEdge = { x: 0.2, y: 0.04, width: 0.2, height: 0.04 };
    const nearBottomMarker = { x: 0.1, y: 0.89, width: 0.1, height: 0.05 };

    expect(moveRect(nearInstanceCode, 0.08, 0, PROTECTED_ZONES)).toBe(nearInstanceCode);
    expect(moveRect(nearTopEdge, 0, -0.03, PROTECTED_ZONES)).toBe(nearTopEdge);
    expect(moveRect(nearBottomMarker, -0.08, 0.06, PROTECTED_ZONES)).toBe(nearBottomMarker);
  });

  it("permits every mutable template lifecycle status", () => {
    expect(canEdit("DRAFT")).toBe(true);
    expect(canEdit("PREFLIGHT_FAILED")).toBe(true);
    expect(canEdit("READY_TO_PUBLISH")).toBe(true);
    expect(canEdit("PUBLISHED")).toBe(false);
    expect(canEdit("DEPRECATED")).toBe(false);
    expect(canEdit("RETIRED")).toBe(false);
  });

  it("snaps normalized geometry to a one millimeter grid and exposes millimeter values", () => {
    const page = { width_mm: 210, height_mm: 297 };
    const snapped = snapRectToMillimeters(
      { x: 0.101, y: 0.203, width: 0.219, height: 0.052 },
      page,
    );

    expect(rectInMillimeters(snapped, page)).toEqual({ x: 21, y: 60, width: 46, height: 15 });
  });

  it("aligns fields to the printable area and rejects protected alignments", () => {
    const original = { x: 0.2, y: 0.4, width: 0.2, height: 0.05 };
    expect(alignRect(original, "horizontal-center", [])).toEqual({ x: 0.4, y: 0.4, width: 0.2, height: 0.05 });
    expect(alignRect({ x: 0.5, y: 0.05, width: 0.2, height: 0.05 }, "right", PROTECTED_ZONES))
      .toEqual({ x: 0.5, y: 0.05, width: 0.2, height: 0.05 });
  });

  it("creates an independent field draft with a unique key", () => {
    const draft = createFieldDraft(["field_3", "field_4"]);
    expect(draft.field_key).toBe("field_5");
    expect(draft.export_target.business_column).toBe("field_5");
    expect(hasDuplicateFieldKey(" field_5 ", [draft])).toBe(true);
  });

  it("clears stale type and recognition configuration when modes change", () => {
    const draft = createFieldDraft([]);
    const numeric = {
      ...draft,
      data_type: "decimal",
      rules: { ...draft.rules, minimum_value: 0, maximum_value: 100 },
      recognition_mode: "DIGIT_OCR" as const,
      recognition_engine: "digit_template",
      fill_policy: "PREFILL_WHEN_CONFIDENT" as const,
      confidence_threshold: 0.97,
      calculation_expression: "hours * rate",
    };

    expect(withDataType(numeric, "text").rules).toMatchObject({ minimum_value: null, maximum_value: null });
    expect(withRecognitionMode(numeric, "NONE")).toMatchObject({
      recognition_engine: "manual",
      fill_policy: "MANUAL_ONLY",
      confidence_threshold: null,
      calculation_expression: null,
    });
    expect(withRecognitionMode(draft, "OMR")).toMatchObject({
      data_type: "boolean",
      paper_entry_mode: "CHECKBOX",
      input_type: "checkbox",
      recognition_mode: "OMR",
    });
    expect(withDataType(numeric, "boolean")).toMatchObject({
      data_type: "boolean",
      recognition_mode: "NONE",
      fill_policy: "MANUAL_ONLY",
      confidence_threshold: null,
    });
  });
});
