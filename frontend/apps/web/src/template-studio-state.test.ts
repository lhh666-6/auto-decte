import { describe, expect, it } from "vitest";

import { nextScreen } from "./template-studio-state";

describe("template studio screen state", () => {
  it("opens a published version in preview and does not create a draft", () => {
    expect(nextScreen({ kind: "library" }, { type: "select", versionId: "TPL-PUBLISHED" }))
      .toEqual({ kind: "preview", versionId: "TPL-PUBLISHED" });
  });

  it("moves from preview to editor only after clone success", () => {
    expect(nextScreen({ kind: "preview", versionId: "TPL-PUBLISHED" }, { type: "cloneSucceeded", versionId: "TPL-DRAFT" }))
      .toEqual({ kind: "editor", versionId: "TPL-DRAFT" });
  });
});
