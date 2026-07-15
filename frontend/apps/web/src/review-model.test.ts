import { describe, expect, it } from "vitest";

import type { EvidenceItem } from "@form-detection/api-client";

import {
  buildConfirmValues,
  reviewValueIssue,
  reviewValueNeedsConfirmation,
  selectReviewEvidence,
} from "./review-model";

function evidence(fileId: string, type: string): EvidenceItem {
  return {
    file_id: fileId,
    type,
    related_field_id: null,
    sha256: `${fileId}-sha`,
    immutable: true,
    created_at: "2026-07-15T00:00:00Z",
    download_url: `/evidence/${fileId}`,
  };
}

describe("buildConfirmValues", () => {
  it("uses an edited field value without mutating the source fields", () => {
    const fields = [
      { fieldId: "quantity", currentValue: 8 },
      { fieldId: "work_order", currentValue: "WO-100" },
    ];

    const values = buildConfirmValues(fields, { quantity: "10" });

    expect(values).toEqual({ quantity: "10", work_order: "WO-100" });
    expect(fields[0].currentValue).toBe(8);
  });
});

describe("reviewValueNeedsConfirmation", () => {
  it("treats a non-empty manual edit as ready despite a low-confidence candidate", () => {
    expect(reviewValueNeedsConfirmation("人工确认值", 0.35, true)).toBe(false);
  });

  it("keeps an untouched low-confidence candidate pending", () => {
    expect(reviewValueNeedsConfirmation("机器候选", 0.35, false)).toBe(true);
  });

  it("accepts numeric zero but keeps blank manual edits pending", () => {
    expect(reviewValueNeedsConfirmation(0, undefined, true)).toBe(false);
    expect(reviewValueNeedsConfirmation("   ", 0.95, true)).toBe(true);
  });
});

describe("reviewValueIssue", () => {
  const baseRules = {
    required: true,
    minimum_value: null,
    maximum_value: null,
    allowed_values: [] as string[],
  };

  it("rejects an invalid enum even when the value is non-empty", () => {
    expect(reviewValueIssue("1", undefined, true, "text", {
      ...baseRules,
      allowed_values: ["白班", "夜班"],
    })).toBe("请选择：白班 / 夜班");
  });

  it("allows an optional blank and validates numeric range", () => {
    expect(reviewValueIssue("", undefined, true, "decimal", {
      ...baseRules,
      required: false,
      minimum_value: 0,
    })).toBeNull();
    expect(reviewValueIssue("-1", undefined, true, "decimal", {
      ...baseRules,
      minimum_value: 0,
    })).toBe("数值不能小于 0");
  });

  it("requires an explicit edit for a low-confidence candidate", () => {
    expect(reviewValueIssue("8", 0.4, false, "integer", baseRules)).toBe(
      "识别置信度较低，请人工确认",
    );
    expect(reviewValueIssue("8", 0.4, true, "integer", baseRules)).toBeNull();
  });
});

describe("selectReviewEvidence", () => {
  it("uses the canonical corrected image for canonical field coordinates", () => {
    const selected = selectReviewEvidence([
      evidence("original", "ORIGINAL_IMAGE"),
      evidence("crop", "FIELD_CROP"),
      evidence("corrected", "CORRECTED_IMAGE"),
    ]);

    expect(selected).toEqual({
      evidence: evidence("corrected", "CORRECTED_IMAGE"),
      coordinateSpace: "canonical",
    });
  });

  it("falls back to the original image without claiming canonical alignment", () => {
    const selected = selectReviewEvidence([evidence("original", "ORIGINAL_IMAGE")]);

    expect(selected.coordinateSpace).toBe("original");
    expect(selected.evidence?.file_id).toBe("original");
  });
});
