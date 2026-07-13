# Template-driven import fallback — progress record

Date: 2026-07-13  
Branch: `modular-architecture`

## Completed

- Added `POST /api/v1/forms/{form_id}/assign-template` for a form in
  `NEEDS_CLASSIFICATION` only.
- The endpoint requires `form.classify`, receives a template key, immutable version,
  and an explicit non-empty reason, then writes a `RECLASSIFY` audit event.
- Resolution is by the exact `template_key + version` pair. Missing, draft,
  deprecated and retired versions are rejected; only `PUBLISHED` can be assigned.

## Verification

- Targeted API tests: published-template success and unpublished-template rejection.
- Ruff check for touched files.
- mypy for the touched backend adapter and router.

## Explicitly still pending

- QR decoding from the controlled uploaded image and automatic template binding.
- Enqueuing a new recognition task after manual classification.
- ArUco-based perspective correction, field crops, and OCR/OMR candidates.

The manual fallback must not be presented as automatic recognition.
