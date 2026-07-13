# Template recognition pipeline — current verified state

Branch: `modular-architecture`  
Date: 2026-07-13

## Implemented and verified

1. Published templates render a checksum-protected IFD QR and four directional ArUco markers.
2. Controlled image import validates the actual image bytes, persists the original evidence,
   and only binds a QR identity when its exact template version exists and is published.
3. Valid templates use ArUco IDs 10/11/12/13 to restore the canonical page canvas. The
   corrected image is separate immutable evidence; incomplete markers safely skip correction.
4. Template field regions are applied only to the canonical canvas. Each crop is immutable
   `FIELD_CROP` evidence and is bound to a stable `form:template-version:field` identity.
5. `digit_template` and `omr` fields create append-only `RecognitionAttempt` candidates;
   `manual` fields do not receive automatic guesses.
6. Each template field freezes its recognition engine and prefill threshold. Publication
   rejects incompatible engine/input/data-type combinations.
7. The full generated-print → import → QR → correction → crop → candidate route has an
   automated acceptance test.

## Explicitly not complete

- Candidate prefill decisions are available as a pure domain rule but are not yet persisted as
  field recognition states or shown as auto-filled editable values in the review workbench.
- Recognition results still need real type/range/master-data/cross-field validation inputs.
- Review queues, draft save, return/void, confirm-and-claim-next and export snapshots remain
  separate implementation work.
- Template package ZIP import/export, paper-instance QR handling, multi-page forms and Tauri
  device adapters are not implemented.

Do not describe a candidate as an approved or confirmed value. Human confirmation remains the
only path to a formal record version.
