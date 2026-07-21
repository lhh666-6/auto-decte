import { describe, expect, it } from "vitest";

import { runtimePolicyForPath } from "./cache-policy";

describe("PWA private-data cache policy", () => {
  it.each([
    "/api/v1/mobile/auth/session",
    "/api/v1/mobile/submissions",
    "/api/v1/mobile/drafts",
    "/api/v1/mobile/context",
    "/api/v1/mobile/active-resources",
    "/api/v1/mobile/available-forms",
    "/api/v1/evidence/file-1",
    "/api/v1/exports/batch-1/download",
    "/downloads/report.xlsx",
    "/evidence/photo.jpg",
  ])("uses NetworkOnly for %s", (path) => {
    expect(runtimePolicyForPath(path)).toBe("NetworkOnly");
  });

  it("does not grant a cache strategy to authenticated reference data", () => {
    expect(runtimePolicyForPath("/api/v1/mobile/options/employees")).toBe("NetworkOnly");
    expect(runtimePolicyForPath("/api/v1/mobile/form-schemas/FORM-A")).toBe("NetworkOnly");
  });
});
