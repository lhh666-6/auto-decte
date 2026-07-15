import { describe, expect, it } from "vitest";

import type { EvidenceItem } from "@form-detection/api-client";

import { buildConfirmValues, selectReviewEvidence } from "./review-model";

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
