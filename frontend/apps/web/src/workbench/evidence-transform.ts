export interface EvidenceTransform {
  readonly zoomPercent: number;
  readonly rotationDegrees: number;
  readonly offsetX: number;
  readonly offsetY: number;
}

export const DEFAULT_EVIDENCE_TRANSFORM: EvidenceTransform = Object.freeze({
  zoomPercent: 100,
  rotationDegrees: 0,
  offsetX: 0,
  offsetY: 0,
});

export function zoomEvidence(
  transform: EvidenceTransform,
  deltaPercent: number,
): EvidenceTransform {
  return {
    ...transform,
    zoomPercent: Math.min(400, Math.max(25, transform.zoomPercent + deltaPercent)),
  };
}

export function rotateEvidenceClockwise(
  transform: EvidenceTransform,
): EvidenceTransform {
  return {
    ...transform,
    rotationDegrees: (transform.rotationDegrees + 90) % 360,
  };
}

export function resetEvidenceTransform(
  _transform: EvidenceTransform,
): EvidenceTransform {
  return { ...DEFAULT_EVIDENCE_TRANSFORM };
}

export function translateEvidence(
  transform: EvidenceTransform,
  deltaX: number,
  deltaY: number,
): EvidenceTransform {
  return {
    ...transform,
    offsetX: transform.offsetX + deltaX,
    offsetY: transform.offsetY + deltaY,
  };
}
