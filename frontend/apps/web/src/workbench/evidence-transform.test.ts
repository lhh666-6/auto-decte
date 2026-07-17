import { describe, expect, it } from "vitest";

import {
  DEFAULT_EVIDENCE_TRANSFORM,
  resetEvidenceTransform,
  rotateEvidenceClockwise,
  translateEvidence,
  zoomEvidence,
} from "./evidence-transform";

describe("evidence transform", () => {
  it("clamps zoom between 25% and 400%", () => {
    expect(zoomEvidence(DEFAULT_EVIDENCE_TRANSFORM, 500).zoomPercent).toBe(400);
    expect(zoomEvidence(DEFAULT_EVIDENCE_TRANSFORM, -500).zoomPercent).toBe(25);
    expect(zoomEvidence(DEFAULT_EVIDENCE_TRANSFORM, 25).zoomPercent).toBe(125);
  });

  it("rotates clockwise in 90 degree steps", () => {
    let transform = DEFAULT_EVIDENCE_TRANSFORM;
    transform = rotateEvidenceClockwise(transform);
    expect(transform.rotationDegrees).toBe(90);
    transform = rotateEvidenceClockwise(transform);
    transform = rotateEvidenceClockwise(transform);
    transform = rotateEvidenceClockwise(transform);
    expect(transform.rotationDegrees).toBe(0);
  });

  it("resets zoom, rotation and displacement", () => {
    const changed = {
      zoomPercent: 225,
      rotationDegrees: 270,
      offsetX: 80,
      offsetY: -35,
    };

    expect(resetEvidenceTransform(changed)).toEqual(DEFAULT_EVIDENCE_TRANSFORM);
  });

  it("translates without changing zoom or rotation", () => {
    expect(translateEvidence({
      zoomPercent: 150,
      rotationDegrees: 90,
      offsetX: 5,
      offsetY: 8,
    }, 12, -3)).toEqual({
      zoomPercent: 150,
      rotationDegrees: 90,
      offsetX: 17,
      offsetY: 5,
    });
  });
});
