import type { EvidenceItem } from "@form-detection/api-client";

export interface ReviewValueField {
  fieldId: string;
  currentValue: unknown;
}

export interface ReviewEvidenceSelection {
  evidence: EvidenceItem | null;
  coordinateSpace: "canonical" | "original" | "none";
}

export function selectReviewEvidence(
  evidence: readonly EvidenceItem[],
): ReviewEvidenceSelection {
  const corrected = evidence.find((item) => item.type === "CORRECTED_IMAGE");
  if (corrected) return { evidence: corrected, coordinateSpace: "canonical" };

  const original = evidence.find((item) => item.type === "ORIGINAL_IMAGE");
  if (original) return { evidence: original, coordinateSpace: "original" };

  return { evidence: null, coordinateSpace: "none" };
}

export function buildConfirmValues(
  fields: readonly ReviewValueField[],
  edits: Readonly<Record<string, unknown>>,
): Record<string, unknown> {
  return Object.fromEntries(
    fields.map((field) => [
      field.fieldId,
      Object.hasOwn(edits, field.fieldId) ? edits[field.fieldId] : field.currentValue,
    ]),
  );
}
