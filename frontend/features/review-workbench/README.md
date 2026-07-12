# review-workbench

**Status:** Contract skeleton — TypeScript interfaces only.

Human-in-the-loop form review UI. Loads raw extraction results, renders them
over the source image for side-by-side comparison, and provides correction
tools for the operator to fix mis-detected fields before finalising.

## Scope

- Load extraction results + source image
- Overlay rendering (field boxes, labels, confidence scores)
- Correction tools (edit field value, re-detect, mark as correct/incorrect)
- Batch operations (approve all, reject all)
- Keyboard shortcuts for fast single-hand operation

## Dependencies

- `@form-detection/api-client` — fetch results, submit corrections
- `@form-detection/shell-ports` — file picker, camera, notifications
- React + React Router
