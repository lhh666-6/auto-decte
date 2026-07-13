import { describe, expect, it } from "vitest";

import { nextScreen } from "./template-studio-state";

describe("template studio screen state", () => {
  it("opens a published version in preview and does not create a draft", () => {
    expect(nextScreen({ kind: "library" }, { type: "select", versionId: "TPL-PUBLISHED" }))
      .toEqual({ kind: "preview", versionId: "TPL-PUBLISHED" });
  });

  it("moves from preview to editor only after clone success", () => {
    expect(nextScreen({ kind: "preview", versionId: "TPL-PUBLISHED" }, { type: "cloneSucceeded", sourceVersionId: "TPL-PUBLISHED", versionId: "TPL-DRAFT" }))
      .toEqual({ kind: "editor", versionId: "TPL-DRAFT" });
  });

  it("keeps the library open when a clone resolves after returning from preview", async () => {
    const clone = deferred<string>();
    let screen = nextScreen({ kind: "library" }, { type: "select", versionId: "TPL-PUBLISHED" });
    const resolution = clone.promise.then((draftId) => {
      screen = nextScreen(screen, { type: "cloneSucceeded", sourceVersionId: "TPL-PUBLISHED", versionId: draftId });
    });

    screen = nextScreen(screen, { type: "backToLibrary" });
    clone.resolve("TPL-DRAFT");
    await resolution;

    expect(screen).toEqual({ kind: "library" });
  });
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}
