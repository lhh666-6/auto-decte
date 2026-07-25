# Legacy Dependency Zero-Reference Audit

**Generated**: 2026-07-25
**Branch**: `modular-architecture`
**HEAD**: `c6dbc0d`
**Scope**: Entire codebase at `d:\半自动表单检测系统`

---

## Detailed Findings

### Module/Symbol: OpenCvImagePipeline
- **Category**: Paper OCR
- **File**: `app/adapters/recognition/opencv.py:31`
- **Status**: BLOCKED_BY: legitimate non-OCR usage
- **Notes**: The class still exists and is actively imported by `app/modules/recognition/facade_ds.py` (quality assessment and perspective correction) and `app/modules/templates/facade_ds.py` (field cropping and QR decoding). These are non-OCR image pipeline utilities. Do NOT delete the class; only OCR-specific methods within it (e.g., digit/OMR recognition) were already removed. 5 test files also use this class legitimately.

---

### Module/Symbol: RecognizeForms (app.application.recognize_forms)
- **Category**: Paper OCR
- **File**: (module deleted; residual imports remain)
- **Status**: CAN_DELETE (broken test files)
- **Notes**: The module `app/application/recognize_forms.py` has been DELETED. However, 3 integration test files still import it and will fail at import time:
  - `tests/integration/test_acceptance_scenarios.py:19`
  - `tests/integration/test_recognition_attempts.py:16`
  - `tests/integration/test_paper_template_acceptance_ds.py:25`
  These test files must either be deleted or have their imports removed/fixed.

---

### Module/Symbol: DIGIT_OCR / HANDWRITING_OCR (RecognitionMode values)
- **Category**: Paper OCR
- **File**: `app/domain/templates_ds.py:210-218`
- **Status**: BLOCKED_BY: used in domain model
- **Notes**: The `RecognitionMode` enum (with values `DIGIT_OCR`, `HANDWRITING_OCR`, `OMR`, `PRINTED_OCR`, `QR`, `NONE`, `CALCULATED`) is defined in `app/domain/templates_ds.py:210` and is NOT dead code. It is used by:
  - `app/application/template_versions_ds.py:313,341` -- preflight validation logic
  - `app/modules/templates/core_payroll_layouts_ds.py:302` -- seed template field specs
  - `tests/unit/test_templates_domain_ds.py` -- domain unit tests
  - `tests/application/test_template_versions_ds.py:209`
  The pairing with `PaperEntryMode` (also in `templates_ds.py:199`) anchors the paper-to-digital template DSL. These enums are the canonical definition; do NOT delete.

---

### Module/Symbol: PaperEntryMode
- **Category**: Paper OCR
- **File**: `app/domain/templates_ds.py:199-208`
- **Status**: BLOCKED_BY: used in domain model
- **Notes**: Same rationale as `RecognitionMode` above. Defined in the domain layer and used pervasively in template definitions, field definitions, and legacy migration helpers within `templates_ds.py` itself.

---

### Module/Symbol: RecognitionMode (enum)
- **Category**: Paper OCR
- **File**: `app/domain/templates_ds.py:210-218`
- **Status**: BLOCKED_BY: used in domain model
- **Notes**: Covered above. Note: while the enum values `DIGIT_OCR`, `HANDWRITING_OCR`, and `OMR` reference retired OCR technologies, the enum itself is the template domain's truth. The individual OCR backends (digits.py, omr.py) are deleted; only the domain type remains, which is correct.

---

### Module/Symbol: TemplatePrintRenderer
- **Category**: Paper OCR
- **File**: (module deleted; was `app/adapters/templates/print_renderer_ds.py`)
- **Status**: CAN_DELETE (broken references)
- **Notes**: The module has been DELETED. Residual broken references exist in:
  - `app/api/routers/templates_ds.py:12` -- **CRITICAL**: imports `ChineseFontUnavailable` from deleted module; this router file is NOT mounted in `main_ds.py` but the file itself cannot even be imported.
  - `tests/adapters/test_template_print_renderer_ds.py` -- entire test file broken (imports deleted module)
  - `tests/modules/test_seed_templates_ds.py:9` -- imports deleted module
  - `tests/integration/test_recognition_attempts.py:13` -- imports deleted module
  - `tests/integration/test_paper_template_acceptance_ds.py:21` -- imports deleted module
  - `app/modules/templates/seed_templates_ds.py:11,155,255` -- commented-out references
  - `app/services/container.py:41,105,172` -- commented-out references

---

### Module/Symbol: print_renderer_ds (module)
- **Category**: Paper OCR
- **File**: N/A (deleted)
- **Status**: ALREADY_RETIRED (same as TemplatePrintRenderer above)
- **Notes**: All same broken references as TemplatePrintRenderer. Additionally, plan documents in `docs/superpowers/plans/` still reference the file path but those are historical docs, not code.

---

### Module/Symbol: payroll_profiles_ds (module)
- **Category**: Paper OCR
- **File**: N/A (deleted; was `app/modules/templates/payroll_profiles_ds.py`)
- **Status**: CAN_DELETE (broken test files)
- **Notes**: The module has been DELETED. Residual broken imports exist in:
  - `tests/modules/test_payroll_profiles_ds.py:14` -- entire file broken
  - `tests/modules/test_seed_templates_ds.py:12`
  - `tests/api/test_review_workbench_api.py:15`
  - `tests/integration/test_paper_template_acceptance_ds.py:28`
  - `tests/integration/test_recognition_attempts.py:30`
  - `tests/integration/test_payroll_xlsx_export_ds.py:23`
  - `tests/adapters/test_template_print_renderer_ds.py:31`
  - `app/modules/templates/seed_templates_ds.py:26` -- commented-out reference
  Its seed template functions were replaced by `core_payroll_layouts_ds.py` and `seed_templates_ds.py`.

---

### Module/Symbol: digits (DigitRecognizer)
- **Category**: Paper OCR
- **File**: N/A (deleted; was `app/adapters/recognition/digits.py`)
- **Status**: CAN_DELETE (broken test files)
- **Notes**: The module has been DELETED. Residual broken imports in:
  - `tests/unit/test_digit_and_omr.py:4` -- imports `DigitRecognizer`
  - `tests/integration/test_acceptance_scenarios.py:12` -- imports `DigitRecognizer`

---

### Module/Symbol: omr (OmrRecognizer)
- **Category**: Paper OCR
- **File**: N/A (deleted; was `app/adapters/recognition/omr.py`)
- **Status**: CAN_DELETE (broken test files)
- **Notes**: The module has been DELETED. Residual broken imports in:
  - `tests/unit/test_digit_and_omr.py:5` -- imports `OmrRecognizer`

---

### Module/Symbol: classification_ds / classification (UI page)
- **Category**: Paper OCR
- **File**: N/A (both deleted)
- **Status**: CAN_DELETE (broken references)
- **Notes**: Both `app/modules/classification_ds.py` and `app/ui/pages/classification.py` have been DELETED. Residual broken references:
  - `app/ui/main.py:11` -- imports `classification` from `app.ui.pages`
  - `app/ui/main.py:40` -- calls `classification.render(services().recognition)` -- `services().recognition` is a commented-out field on the Services dataclass, so this would also fail
  - `tests/unit/test_classification_page.py:5` -- imports from deleted `app.ui.pages.classification`
  - `tests/api/test_imports_api_ds.py:389` -- references `services.recognition` (attribute no longer exists)

---

### Module/Symbol: candidates (module)
- **Category**: Paper OCR
- **File**: N/A (deleted)
- **Status**: ALREADY_RETIRED
- **Notes**: No direct imports of the deleted `candidates.py` module were found. The word "candidates" appears only as a variable name in unrelated contexts (field candidates lists, reporting handler, etc.). No cleanup needed.

---

### Module/Symbol: import_page (Streamlit UI page)
- **Category**: Paper OCR
- **File**: N/A (deleted; was `app/ui/pages/import_page.py`)
- **Status**: CAN_DELETE (broken reference in ui/main.py)
- **Notes**: The module has been DELETED. Residual broken reference:
  - `app/ui/main.py:11` -- imports `import_page` from `app.ui.pages`
  - `app/ui/main.py:38` -- calls `import_page.render(services().imports)`

---

### Module/Symbol: build_paper_acceptance_pack_ds
- **Category**: Paper OCR
- **File**: N/A (deleted; was `app/tools/build_paper_acceptance_pack_ds.py`)
- **Status**: CAN_DELETE (broken test file)
- **Notes**: The module has been DELETED. Residual broken import:
  - `tests/tools/test_build_paper_acceptance_pack_ds.py:8` -- imports from deleted module

---

### Module/Symbol: legacy_archive_* tables
- **Category**: Paper OCR
- **File**: `alembic/versions/037_retire_legacy_archive_tables.py`
- **Status**: ALREADY_RETIRED
- **Notes**: Migration 037 drops all 8 `legacy_archive_*` tables. No application code references these tables. References exist only in:
  - Alembic migration files (expected)
  - `scripts/retire_legacy_recognition.py` (the cleanup script itself)
  - Test files for retirement migration verification
  No further action needed.

---

### Module/Symbol: WorkflowDesigner / workflow_engine
- **Category**: Old Platform
- **File**: `app/modules/workflow_engine/`
- **Status**: BLOCKED_BY: active feature
- **Notes**: This is NOT legacy code. It is the current workflow engine used by both the admin console and finance workspace. The module is fully functional with a service, preflight, and database backing. The `WorkflowDesignerPage` frontend component is live at `/finance/workflows`. Do NOT delete.

---

### Module/Symbol: BusinessDiscoveryService / business_discovery
- **Category**: Old Platform
- **File**: `app/modules/business_discovery/`
- **Status**: BLOCKED_BY: active feature
- **Notes**: This is NOT legacy code. It is the current business discovery module with full service implementation (`service_ds.py`), database tables (`business_discovery_sessions`, `business_discovery_messages`), and API endpoints in `finance_workspace_ds.py`. Frontend `BusinessModelingPage` is live at `/finance/business-modeling`. Do NOT delete.

---

### Module/Symbol: BusinessModeling / business_modeling
- **Category**: Old Platform
- **File**: `frontend/apps/web/src/web/BusinessModelingPage.tsx`
- **Status**: BLOCKED_BY: active feature
- **Notes**: Active frontend page at `/finance/business-modeling`. The route is defined in `router.tsx:125`. Do NOT delete.

---

### Module/Symbol: ReportMapping / report_mapping
- **Category**: Old Platform
- **File**: `app/modules/report_templates/service_ds.py`
- **Status**: BLOCKED_BY: active feature
- **Notes**: This is NOT legacy. It is part of the current report template mapping system. The `ReportMappingVersionRow` model, `report_mapping_versions` table, API endpoints, and `FinanceReportTemplatesPage` frontend are all active. Do NOT delete.

---

### Module/Symbol: AI Mapping / ai_mapping
- **Category**: Old Platform
- **File**: N/A
- **Status**: ALREADY_RETIRED
- **Notes**: No references to "AI Mapping" or "ai_mapping" were found anywhere in the codebase. This concept was either never implemented or was fully removed in a prior cleanup.

---

### Module/Symbol: ReportTemplate (arbitrary, not managed form)
- **Category**: Old Platform
- **File**: `app/modules/report_templates/service_ds.py`
- **Status**: BLOCKED_BY: active feature
- **Notes**: This IS the new managed report template system (XLSX upload, safety validation, mapping, governed export). It is actively used by `FinanceReportTemplatesPage`, `AdminReportTemplatesPage`, `FinanceGovernedExportsPage`, and has API endpoints in both `admin_console_ds.py` and `finance_workspace_ds.py`. Do NOT delete. Note: this is distinct from the old Paper OCR "TemplatePrintRenderer" system.

---

### Module/Symbol: AppRouter templates_ds.py
- **Category**: Route
- **File**: `app/api/routers/templates_ds.py:12`
- **Status**: CAN_DELETE (broken, unmounted file)
- **Notes**: This router file imports `ChineseFontUnavailable` from the deleted `print_renderer_ds` module at line 12. The import will fail at module load time. However, this router is NOT mounted in either `app/api/main.py` or `app/api/main_ds.py` (the main_ds.py mounts only: health, mobile, web_auth, admin_console, admin_audit, finance_workspace, plant_workspace). The file is dead, broken code.

---

### Module/Symbol: workbench/ directory (all files)
- **Category**: Frontend Dead Code
- **File**: `frontend/apps/web/src/workbench/` (30 files exist)
- **Status**: CAN_DELETE (all files reference deleted API types)
- **Notes**: The entire workbench directory still exists with 30 files: BatchImportPanel.tsx, BatchImportPanel.test.tsx, ClassificationStage.tsx, ClassificationStage.test.tsx, evidence-transform.ts, evidence-transform.test.ts, EvidenceToolbar.tsx, EvidenceViewer.tsx, EvidenceViewer.test.tsx, field-behavior.ts, field-navigation.ts, field-navigation.test.ts, FieldDetailPanel.tsx, FieldDetailPanel.test.tsx, FieldReviewTable.tsx, FieldReviewTable.test.tsx, ImportOverview.tsx, ImportOverview.test.tsx, RecaptureStage.tsx, RecaptureStage.test.tsx, RecognitionProgress.tsx, ReviewWorkbenchPage.tsx, ReviewWorkbenchPage.test.tsx, useWorkbenchShortcuts.ts, useWorkbenchShortcuts.test.tsx, workbench-types.ts, WorkbenchActionBar.tsx, WorkbenchEmptyState.tsx, WorkbenchHeader.tsx, WorkbenchQueue.tsx.
  
  Key files with broken imports:
  - `ImportOverview.tsx:1` -- imports `ImportApi`, `ImportedImageSummary` from `@form-detection/api-client` (both retired)
  - `ReviewWorkbenchPage.tsx:3,64` -- imports and instantiates `ImportApi`
  - `BatchImportPanel.tsx:1` -- imports `ImportApi`
  - `BatchImportPanel.test.tsx:7` -- imports `ImportApi`
  - `ImportOverview.test.tsx:7` -- imports `ImportApi`
  - `ClassificationStage.tsx` -- references paper OCR classification workflow
  - `RecaptureStage.tsx` -- references paper OCR recapture workflow
  - `RecognitionProgress.tsx` -- references OCR recognition progress
  No workbench routes exist in `router.tsx`. The entire directory and `frontend/apps/web/src/import-api.test.ts` should be deleted.

---

### Module/Symbol: ImportedImageSummary (API client type)
- **Category**: Frontend Dead Code
- **File**: `frontend/packages/api-client/src/index_ds.ts` (retired)
- **Status**: CAN_DELETE (still imported by dead workbench code)
- **Notes**: The type was removed from the API client's public exports (`index_ds.ts:14-15,63` has comments "TemplateApi -- retired", "ImportApi -- retired", "ImportApi (Paper OCR retired)"). However, `frontend/apps/web/src/workbench/ImportOverview.tsx:1` still imports it. Since the workbench code is also dead, this is a transitive break.

---

### Module/Symbol: ImportApi (API client class)
- **Category**: Frontend Dead Code
- **File**: `frontend/packages/api-client/src/index_ds.ts` (retired)
- **Status**: CAN_DELETE (same rationale as ImportedImageSummary)
- **Notes**: Retired from the API client but still imported by:
  - `frontend/apps/web/src/workbench/ImportOverview.tsx:1`
  - `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx:3`
  - `frontend/apps/web/src/workbench/BatchImportPanel.tsx:1`
  - `frontend/apps/web/src/workbench/BatchImportPanel.test.tsx:7`
  - `frontend/apps/web/src/workbench/ImportOverview.test.tsx:7`
  - `frontend/apps/web/src/import-api.test.ts:3` (standalone test file)

---

### Module/Symbol: TemplateApi (API client class)
- **Category**: Frontend Dead Code
- **File**: `frontend/packages/api-client/src/index_ds.ts:14` (retired)
- **Status**: ALREADY_RETIRED
- **Notes**: Marked as retired in the API client index. No active imports found in the frontend application code. Only referenced in docs and historical plans.

---

### Module/Symbol: Template Studio files (TemplateStudio_ds.tsx, etc.)
- **Category**: Frontend Dead Code
- **File**: N/A (all deleted)
- **Status**: ALREADY_RETIRED
- **Notes**: All Template Studio frontend files have been deleted:
  - `TemplateStudio_ds.tsx` -- DELETED
  - `TemplateStudio_ds.test.tsx` -- DELETED
  - `TemplateLibrary_ds.tsx` -- DELETED
  - `TemplateLibrary_ds.test.tsx` -- DELETED
  - `TemplateCanvasEditor_ds.tsx` -- DELETED
  - `TemplatePreview_ds.tsx` -- DELETED
  - `FieldInspector_ds.tsx` -- DELETED
  - All related model/state files -- DELETED
  No residual imports found. Only historical references in docs and plan files.

---

### Module/Symbol: Services.recognition attribute
- **Category**: Container
- **File**: `app/services/container.py:112` (commented out)
- **Status**: CAN_DELETE (one residual test reference)
- **Notes**: The `recognition` field on the `Services` dataclass is commented out at line 112 (`# OCR retired: recognition`). However, one test still references it:
  - `tests/api/test_imports_api_ds.py:389` -- `monkeypatch.setattr(services.recognition, "record_template_field_crops", fail_crops)`
  This test will fail with `AttributeError` if run.

---

### Module/Symbol: container.py -- ImportForms, ReviewForms, AIReviewForms
- **Category**: Container
- **File**: `app/services/container.py:47,54,43`
- **Status**: BLOCKED_BY: active services (not Paper OCR)
- **Notes**: These are the CURRENT (non-OCR) form management services:
  - `ImportForms` -- evidence/image import for forms
  - `ReviewForms` -- human confirmation/correction of form values
  - `AIReviewForms` -- AI-assisted review suggestions
  These are distinct from the retired `RecognizeForms` (OCR recognition). They operate on domain models, not images. Do NOT delete.

---

### Module/Symbol: app/ui/main.py (Streamlit entry point)
- **Category**: Route
- **File**: `app/ui/main.py:11,38,40`
- **Status**: NEEDS_STUB (broken imports for classification and import_page)
- **Notes**: This Streamlit entry point is BROKEN at import time:
  - Line 11: imports `classification` from `app.ui.pages` -- module deleted
  - Line 11: imports `import_page` from `app.ui.pages` -- module deleted
  - Line 40: calls `classification.render(services().recognition)` -- both deleted
  - Line 38: calls `import_page.render(services().imports)` -- module deleted
  The Streamlit UI is an alternate frontend; the main web frontend does not use it. Either remove the Streamlit UI entirely or add stubs/placeholders for the deleted pages.

---

## Summary: BROKEN Files Requiring Immediate Attention

These files will fail at import/compile time:

### Backend (Python -- import-time failures):

| # | File | Broken Import |
|---|------|---------------|
| 1 | `app/api/routers/templates_ds.py:12` | `ChineseFontUnavailable` from deleted `print_renderer_ds` |
| 2 | `app/ui/main.py:11` | `classification`, `import_page` from deleted UI pages |
| 3 | `tests/unit/test_classification_page.py:5` | `InvalidImageError, decode_image` from deleted `app.ui.pages.classification` |
| 4 | `tests/unit/test_digit_and_omr.py:4-5` | `DigitRecognizer`, `OmrRecognizer` from deleted modules |
| 5 | `tests/adapters/test_template_print_renderer_ds.py:10-12` | `TemplatePrintRenderer`, `ChineseFontUnavailable` from deleted module |
| 6 | `tests/modules/test_seed_templates_ds.py:9,12` | `TemplatePrintRenderer` (deleted), `payroll_profiles_ds` (deleted) |
| 7 | `tests/modules/test_payroll_profiles_ds.py:14` | Everything from deleted `payroll_profiles_ds` |
| 8 | `tests/api/test_review_workbench_api.py:15` | `reviewed_payroll_seed_templates` from deleted `payroll_profiles_ds` |
| 9 | `tests/api/test_imports_api_ds.py:389` | `services.recognition` (AttributeError at runtime) |
| 10 | `tests/integration/test_acceptance_scenarios.py:12,13,17,19-20` | `DigitRecognizer`, `OpenCvImagePipeline`, `ImportForms`, `RecognizeForms`, `ReviewForms` |
| 11 | `tests/integration/test_recognition_attempts.py:11,13,16-17,30` | `OpenCvImagePipeline`, `TemplatePrintRenderer`, `RecognizeForms`, `ReviewForms`, `payroll_profiles_ds` |
| 12 | `tests/integration/test_paper_template_acceptance_ds.py:19,21,23,25-26,28` | `OpenCvImagePipeline`, `TemplatePrintRenderer`, `ImportForms`, `RecognizeForms`, `ReviewForms`, `payroll_profiles_ds` |
| 13 | `tests/integration/test_payroll_xlsx_export_ds.py:23,26` | `payroll_profiles_ds`, `seed_templates_ds.legacy_payroll_seed_templates` |
| 14 | `tests/tools/test_build_paper_acceptance_pack_ds.py:8` | Everything from deleted `build_paper_acceptance_pack_ds` |

### Frontend (TypeScript -- compile-time failures):

| # | File | Broken Import |
|---|------|---------------|
| 15 | `frontend/apps/web/src/workbench/ImportOverview.tsx:1` | `ImportApi`, `ImportedImageSummary` (retired from API client) |
| 16 | `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx:3` | `ImportApi` (retired) |
| 17 | `frontend/apps/web/src/workbench/BatchImportPanel.tsx:1` | `ImportApi` (retired) |
| 18 | `frontend/apps/web/src/workbench/BatchImportPanel.test.tsx:7` | `ImportApi` (retired) |
| 19 | `frontend/apps/web/src/workbench/ImportOverview.test.tsx:7` | `ImportApi` (retired) |
| 20 | `frontend/apps/web/src/import-api.test.ts:3` | `ImportApi` (retired) |

---

## Router Mount Summary

### `app/api/main.py`
- Delegates to `app/api/main_ds.py` with injected `Services`

### `app/api/main_ds.py`
Mounted routers (7 total):
| Router | Module |
|--------|--------|
| health | `app.api.routers.health_ds` |
| mobile | `app.api.routers.mobile_ds` |
| web_auth | `app.api.routers.web_auth_ds` |
| admin_console | `app.api.routers.admin_console_ds` |
| admin_audit | `app.api.routers.admin_console_ds_audit` |
| finance_workspace | `app.api.routers.finance_workspace_ds` |
| plant_workspace | `app.api.routers.plant_workspace_ds` |

NOT mounted (but file exists, broken): `app.api.routers.templates_ds`

### `frontend/apps/web/src/app/router.tsx`
All active routes. No workbench routes. No Template Studio routes. The finance workspace has 14 routes, admin has 13, plant has 8, and mobile has 7.

---

## Services Container Summary (`app/services/container.py`)

### Active service fields on the `Services` dataclass (33 total):
settings, engine, repository, template_repository, report_definition_repository, templates, job_profiles, imports, reviews, queries, exports, reporting, export_handler, ai_reviews, report_assistant, vector_index, review_leases, review_repository, review_facade, task_store, tasks, evidence_storage, master_data_repository, master_data, fact_record_repository, fact_records, electronic_integration, mobile_identity_repository, mobile_identity, electronic_definition_repository, electronic_definitions, bamboo_repository, bamboo_process, bamboo_operations

### Commented-out (retired) fields:
- Line 105: `# OCR retired: template_renderer`
- Line 112: `# OCR retired: recognition`

### Commented-out (retired) imports:
- Line 38: `# from app.adapters.recognition.opencv import OpenCvImagePipeline`
- Line 41: `# OCR retired: TemplatePrintRenderer`
- Line 52: `# OCR retired: RecognizeForms`
- Line 88: `# OCR retired: install_legacy_payroll_seed_templates`

---

## Summary Table

| Category | CAN_DELETE | BLOCKED | NEEDS_STUB | ALREADY_RETIRED | Total |
|----------|-----------|---------|------------|-----------------|-------|
| Paper OCR | 9 | 4 | 0 | 3 | 16 |
| Old Platform | 0 | 5 | 0 | 1 | 6 |
| Frontend Dead Code | 3 | 0 | 0 | 2 | 5 |
| Route | 1 | 0 | 1 | 0 | 2 |
| Container | 1 | 1 | 0 | 0 | 2 |
| **TOTAL** | **14** | **10** | **1** | **6** | **31** |

### Legend:
- **CAN_DELETE**: The reference is to a deleted module; the referencing file is broken and should be removed/fixed.
- **BLOCKED_BY**: The module/symbol is still legitimately used by active code. Do NOT delete.
- **NEEDS_STUB**: The reference is broken but the referencing file (Streamlit UI) may need placeholder stubs rather than outright deletion.
- **ALREADY_RETIRED**: Fully retired; no residual references found.

---

## Action Items (Priority Order)

### P0 -- Fix Import-Time Breakages (will crash on import)
1. Delete `app/api/routers/templates_ds.py` (unmounted, broken import from deleted module)
2. Fix or delete `app/ui/main.py` (broken imports of `classification` and `import_page`)
3. Delete all 14 broken test files listed above, OR remove the broken import lines

### P1 -- Clean Up Frontend Dead Code
4. Delete the entire `frontend/apps/web/src/workbench/` directory (30 files)
5. Delete `frontend/apps/web/src/import-api.test.ts`
6. Verify that `frontend/packages/api-client/src/index_ds.ts` cleaned up all retired exports

### P2 -- Document Design Decisions
7. Add comments in `app/domain/templates_ds.py` clarifying that `PaperEntryMode` and `RecognitionMode` enums are the canonical template domain types (not legacy OCR) and should remain until template DSL is redesigned
8. Verify the `app/modules/recognition/facade_ds.py` facade is still needed (it wraps OpenCvImagePipeline for quality assessment/perspective correction)

---

## Notes

- The word "classification" in `app/ui/main.py` refers to the deleted Streamlit page, NOT the deleted `classification_ds.py` module. Both are gone.
- `services.recognition` attribute was a field on the `Services` dataclass that held the `RecognizeForms` instance. Both the attribute and the class have been retired.
- The `app/modules/recognition/` facade still exists because it wraps `OpenCvImagePipeline` for non-OCR image utilities (quality assessment, perspective correction). This is intentionally preserved.
- `app/adapters/recognition/opencv.py` still exists (only `digits.py` and `omr.py` were deleted from that directory).
- The "Old Platform" items (WorkflowDesigner, BusinessDiscovery, BusinessModeling, ReportMapping, ReportTemplate) are all ACTIVE features in the current architecture. They were flagged for audit due to naming ambiguity but are confirmed alive and functioning.
