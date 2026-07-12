# templates

**Status:** Contract skeleton — TypeScript interfaces only.

Template extraction configuration UI. Allows power users to define and test
extraction templates (field regions, OCR settings, post-processing rules)
without backend deployment.

## Scope

- Template list / search
- Template editor (drag-and-drop field region definition)
- Region-of-interest calibration (pixel coordinate mapping)
- Extraction parameter tuning (OCR engine, confidence threshold, language)
- Template versioning and diff view
- In-browser preview / test extraction

## Dependencies

- `@form-detection/api-client` — template CRUD, test extraction
- `@form-detection/shell-ports` — file picker for test image upload
- React + canvas or SVG overlay library
