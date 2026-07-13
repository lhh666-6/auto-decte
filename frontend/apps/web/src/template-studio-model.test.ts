import { describe, expect, it } from "vitest";

import { QR_SAFE_ZONE, canEdit, isProtectedOverlap, moveRect, resizeRect } from "./template-studio-model";

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

  it("permits edits only for draft versions", () => {
    expect(canEdit("DRAFT")).toBe(true);
    expect(canEdit("PUBLISHED")).toBe(false);
  });
});
