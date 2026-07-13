export type StudioScreen =
  | { kind: "library" }
  | { kind: "preview"; versionId: string }
  | { kind: "editor"; versionId: string };

export type StudioAction =
  | { type: "select"; versionId: string }
  | { type: "cloneSucceeded"; sourceVersionId: string; versionId: string }
  | { type: "draftCreated"; versionId: string }
  | { type: "editDraft"; versionId: string }
  | { type: "backToLibrary" };

export function nextScreen(screen: StudioScreen, action: StudioAction): StudioScreen {
  switch (action.type) {
    case "select":
      return { kind: "preview", versionId: action.versionId };
    case "cloneSucceeded":
      return screen.kind === "preview" && screen.versionId === action.sourceVersionId
        ? { kind: "editor", versionId: action.versionId }
        : screen;
    case "draftCreated":
    case "editDraft":
      return { kind: "editor", versionId: action.versionId };
    case "backToLibrary":
      return { kind: "library" };
  }
}
