import { useEffect, useRef } from "react";

export type ImageShortcutCommand = "zoom-in" | "zoom-out" | "reset" | "rotate";

interface WorkbenchShortcutOptions {
  fieldIds: string[];
  issueFieldIds: string[];
  selectedFieldId: string | null;
  hasLease: boolean;
  hasUnsavedEdits: boolean;
  onAcceptCandidate(): void;
  onSelectField(fieldId: string): void;
  onSaveDraft(): void;
  onImageCommand(command: ImageShortcutCommand): void;
}

export function useWorkbenchShortcuts(options: WorkbenchShortcutOptions) {
  const current = useRef(options);
  current.current = options;

  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      const settings = current.current;
      const target = event.target instanceof Element ? event.target : null;
      const tagName = target?.tagName;
      const isComposing = event.isComposing || event.keyCode === 229;

      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        if (settings.hasLease && settings.hasUnsavedEdits) {
          event.preventDefault();
          settings.onSaveDraft();
        }
        return;
      }

      if (event.key === "Tab" && settings.selectedFieldId && settings.fieldIds.length > 0) {
        const currentIndex = settings.fieldIds.indexOf(settings.selectedFieldId);
        const direction = event.shiftKey ? -1 : 1;
        const nextIndex = (Math.max(0, currentIndex) + direction + settings.fieldIds.length)
          % settings.fieldIds.length;
        settings.onSelectField(settings.fieldIds[nextIndex]);
        return;
      }

      if (event.key === "Enter") {
        if (isComposing || tagName === "TEXTAREA" || tagName === "SELECT" || tagName === "BUTTON") {
          return;
        }
        event.preventDefault();
        settings.onAcceptCandidate();
        const currentIndex = settings.issueFieldIds.indexOf(settings.selectedFieldId ?? "");
        if (settings.issueFieldIds.length > 1 && currentIndex >= 0) {
          const nextIndex = (currentIndex + 1) % settings.issueFieldIds.length;
          settings.onSelectField(settings.issueFieldIds[nextIndex]);
        }
        return;
      }

      const imageContext = target?.closest("[data-workbench-image-context]");
      if (!imageContext || isComposing) {
        return;
      }

      const key = event.key.toLowerCase();
      const command: ImageShortcutCommand | null =
        key === "+" || key === "=" ? "zoom-in"
          : key === "-" ? "zoom-out"
            : key === "0" ? "reset"
              : key === "r" ? "rotate"
                : null;
      if (command) {
        event.preventDefault();
        settings.onImageCommand(command);
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);
}
