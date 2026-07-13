export type StudioScreen =
  | { kind: "library" }
  | { kind: "preview"; versionId: string }
  | { kind: "editor"; versionId: string };

export type StudioAction =
  | { type: "select"; versionId: string }
  | { type: "cloneSucceeded"; versionId: string }
  | { type: "draftCreated"; versionId: string }
  | { type: "editDraft"; versionId: string }
  | { type: "backToLibrary" };

export function nextScreen(_screen: StudioScreen, action: StudioAction): StudioScreen {
  switch (action.type) {
    case "select":
      return { kind: "preview", versionId: action.versionId };
    case "cloneSucceeded":
    case "draftCreated":
    case "editDraft":
      return { kind: "editor", versionId: action.versionId };
    case "backToLibrary":
      return { kind: "library" };
  }
}
