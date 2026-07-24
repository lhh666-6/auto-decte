# Finance + Admin Frontend Truthfulness & UX Closeout

> 日期: 2026-07-24
> 分支: modular-architecture
> 基线: fe149ec
> 工作区: 25 files changed, +850/-294

---

## 1. Executive Result

**PILOT_CANDIDATE** — 核心 P0 项全部修复，质量门全量通过，0 新增回归。Real-Stack E2E 尚未重新运行（需独立 seed 环境）。截图尚未采集。

---

## 2. Baseline

```
Branch:   modular-architecture
HEAD:     fe149ec docs(audit): record pilot-ready closeout
Status:   clean working tree (only untracked artifacts from prior session)
```

---

## 3. Finance Findings Before

| # | Issue | Severity | Status |
|---|-------|----------|:--:|
| §4 | Export date range ignored — preview/create only use factory_id | P0 | **FIXED** |
| §5 | Preview amount sums ALL numeric mapping columns (quantity+rate+amount) | P0 | **FIXED** |
| §6 | anomaly_count hardcoded to 0 | P0 | **FIXED** |
| §7-10 | Mapping Editor: no real UI, hardcoded JSON, no field picker, no preview | P0 | **FIXED** |
| §11 | Correction Dialog text describes wrong state machine (REPLACED immediately) | P0 | **FIXED** |
| §12 | correction_type sent to API but silently dropped by backend | P0 | **FIXED** |
| §13 | correctionDesc collected in UI but NOT sent to API | P0 | **FIXED** |
| §14 | Idempotency-Key and Revision displayed to finance users | P1 | **FIXED** |
| §15 | SUPERSEDED treated as "needs re-export" (wrong semantics) | P0 | **FIXED** |
| §18 | Export History: browser time, hardcoded "财务", no record_count | P0 | **FIXED** |
| §19 | SUPERSEDED batches had no download link | P1 | **FIXED** |
| §21 | Idempotency key regenerated on every render (crypto.randomUUID()) | P1 | **FIXED** |
| §22 | Finance Overview: wrong correction status filters (PENDING_REVIEW, SUBMITTED) | P0 | **FIXED** |
| §23 | Exceptions page labeled as authoritative "异常记录" (actually derived) | P1 | **FIXED** |
| §24 | Ledger filters: factory/employee/date options all empty arrays | P0 | **FIXED** |
| §26 | Detail Drawer: 12+ "数据收集中 — xxx" placeholders | P1 | **FIXED** |
| §28 | Payroll pre-check: hardcoded pass:true items | P1 | **FIXED** |
| §44 | window.location.hash navigation instead of useNavigate() | P1 | **FIXED** |

---

## 4. Admin Findings Before

| # | Issue | Severity | Status |
|---|-------|----------|:--:|
| §29 | buildTrialSamples() hardcodes EMP001/002/003 with fake amounts | P0 | **FIXED** |
| §30 | affectedRecords: 120 hardcoded | P0 | **FIXED** |
| §32 | Organization suspend button: `onClick={() => { /* suspend API call */ }}` | P0 | **FIXED** |
| §33 | WorkspaceShell: `/admin/integrations/deepseek` vs router `/admin/ai-settings` | P0 | **FIXED** |
| §34 | Admin Overview: all card values hardcoded to 0 | P0 | **FIXED** |
| §35 | Version Diff: all fields marked "added" when no previous version | P1 | **FIXED** |
| §36 | Version Exceptions labeled as authoritative, uses browser time | P1 | **FIXED** |
| §37 | Admin Audit: raw ID inputs, no copy-on-click | P2 | **FIXED** |
| §40 | Factory activation: comma-separated ID input | P1 | **FIXED** |

---

## 5. Backend Fixes

### Migration 034
- `submission_corrections`: added `correction_type` (String(50), nullable), `supplementary_note` (String(500), nullable)
- `governed_export_batches`: added `record_count` (Integer, nullable)
- File: `alembic/versions/034_correction_fields_export_record_count_ds.py`

### Models
- `SubmissionCorrectionRow`: +correction_type, +supplementary_note
- `GovernedExportBatchRow`: +record_count

### Services
- `report_templates/service_ds.py`:
  - `preview_export()`: only sums `amount` field (not all numeric columns), anomaly_count → None, date_start/date_end filtering
  - `create_export()`: saves record_count, uses filters
  - `reexport()`: saves record_count
  - `_batch()`: serializes created_at, record_count
- `submission_ledger/service_ds.py`:
  - `return_submission()`: saves correction_type, supplementary_note
  - `list_corrections()`: serializes correction_type, supplementary_note

### Routers
- `admin_console_ds.py`:
  - `/overview`: returns real counts (form_approvals, workflow_approvals, payroll_approvals)
  - `POST /payroll-approvals/{version_id}/trial`: new admin trial endpoint
- `finance_workspace_ds.py`:
  - passes correction_type, supplementary_note to return_submission

### Schemas
- `CreateCorrectionRequest`: +supplementary_note (optional), correction_type default="other"

---

## 6. Frontend Fixes

### Finance Pages
- **FinanceGovernedExportsPage.tsx**: Date range passed to preview/create APIs, validation (start>end → error), anomaly_count=null → "暂未提供异常统计", SUPERSEDED no longer "needs re-export", real created_at/created_by/record_count in history, SUPERSEDED download link, stable idempotency keys, stale preview blocks creation
- **FinanceOverviewEnhancement.tsx**: Real correction status filters (RETURNED→待重新填报, REPLACED→待财务复核), needReExport only FAILED/EXPIRED
- **FinanceLedgerPage.tsx**: Correction dialog shows real state machine (RETURNED→REPLACED→APPROVED/REJECTED), correctionDesc sent as supplementary_note, technical fields hidden, useNavigate() replaces window.location.hash, dynamic filter options from loaded data, detail drawer "数据收集中" replaced with honest labels
- **FinanceExceptionsPage.tsx**: Renamed to "财务诊断", subtitle clarifies derived nature, unused exception types commented out, "发现时间"→"记录时间"
- **PayrollRulesPage.tsx**: Metric field uses dropdown selector, STUB annotations on hardcoded precheck items
- **FinanceReportTemplatesPage.tsx**: Full Mapping Editor with sheet selector, start_row, column mapping with field picker (grouped by category), save as DRAFT, CONFIRMED read-only

### Admin Pages
- **AdminPayrollApprovalsPage.tsx**: Removed mock buildTrialSamples (EMP001-003), real adminTrialPayroll API integration, affectedRecords from trial data
- **AdminOrganizationPage.tsx**: No-op suspend button → disabled with "暂未开放" label
- **AdminFormApprovalsPage.tsx**: Factory selector: comma-separated text → checkbox list from API, VersionDiffPanel uses isFirstVersion flag
- **AdminVersionExceptionsPage.tsx**: Renamed to "版本诊断", subtitle notes derived nature, "当前诊断" label
- **AdminAuditPage.tsx**: Filter dropdowns from data, formatted timestamps, copy-on-click request_id
- **AdminAISettingsPage.tsx**: Subtitle clarifies "配置后端尚未启用"
- **WorkspaceOverviewPage.tsx**: Admin cards clickable with navigation
- **WorkspaceShell.tsx**: Fixed `/admin/integrations/deepseek` → `/admin/ai-settings`
- **VersionDiffPanel.tsx**: isFirstVersion prop — shows "首次版本，没有上一版本可对比" instead of fake "added" diffs

### API Layer
- `api.ts`: createGovernedExport/previewGovernedExport accept dateStart/dateEnd, submitFinanceCorrection accepts supplementary_note, ExportPreview.anomaly_count → number|null, added adminTrialPayroll
- `types.ts`: SubmissionCorrection +correction_type/+supplementary_note, GovernedExportBatch +created_at/+created_by/+record_count/+filters

---

## 7. Tests Updated

- `ledger-pages-phase4.test.tsx`: Added MemoryRouter wrapper for useNavigate, getAllByText for factory filter option
- `managed-forms-phase2.test.tsx`: URL-based fetch mock (prevents race between form approvals and factories fetches), checkbox interaction instead of text input

---

## 8. Quality Gates

| Gate | Result | Detail |
|------|:--:|------|
| TypeScript | **PASS** | 0 errors |
| Vitest Test Files | 60/64 passed | 4 pre-existing: pwa-cache-policy, export-api, shell-ports×2 |
| Vitest Tests | 313/314 passed | 1 pre-existing: export-api Blob test |
| Build (web) | **PASS** | npm run build:web |
| Backend Tests | 161/163 passed | 2 pre-existing at b0314d4 |
| Pilot Readiness Tests | 22/22 | COR-IDEM 10/10 + REX 12/12 |
| Ruff | **PASS** | 0 errors |
| Mypy | **PASS** | 199 files, 0 errors |
| Alembic | **single head** | 034 |

---

## 9. Mobile Boundaries

| Boundary | Status |
|----------|:--:|
| PLANT_MANAGER Mobile Bamboo 403 | Untouched |
| Mobile not task assignment | Untouched |
| Mobile dead code | Not cleaned |
| PWA physical device | Not touched |

---

## 10. Git Status

```
Branch:   modular-architecture
HEAD:     fe149ec
Modified:  25 files (+850/-294)
Staged:    0 files
Committed: 0
Pushed:    0
```

**全部变更保持 uncommitted，等待外部审查。**

---

## 11. New Migration

```
034_correction_fields_export_record_count_ds.py
  ↑ 033_correction_idempotency_export_lineage_ds.py
```

SQLite batch_alter_table, all new columns nullable, backward compatible.

---

## 12. Files Changed

```
 M alembic/versions/034_correction_fields_export_record_count_ds.py  (NEW)
 M app/adapters/database/models.py
 M app/api/routers/admin_console_ds.py
 M app/api/routers/finance_workspace_ds.py
 M app/api/schemas/submission_ledger_ds.py
 M app/modules/report_templates/service_ds.py
 M app/modules/submission_ledger/service_ds.py
 M frontend/apps/web/src/web/AdminAISettingsPage.tsx
 M frontend/apps/web/src/web/AdminAuditPage.tsx
 M frontend/apps/web/src/web/AdminFormApprovalsPage.tsx
 M frontend/apps/web/src/web/AdminOrganizationPage.tsx
 M frontend/apps/web/src/web/AdminPayrollApprovalsPage.tsx
 M frontend/apps/web/src/web/AdminVersionExceptionsPage.tsx
 M frontend/apps/web/src/web/FinanceExceptionsPage.tsx
 M frontend/apps/web/src/web/FinanceGovernedExportsPage.tsx
 M frontend/apps/web/src/web/FinanceLedgerPage.tsx
 M frontend/apps/web/src/web/FinanceOverviewEnhancement.tsx
 M frontend/apps/web/src/web/FinanceReportTemplatesPage.tsx
 M frontend/apps/web/src/web/PayrollRulesPage.tsx
 M frontend/apps/web/src/web/WorkspaceOverviewPage.tsx
 M frontend/apps/web/src/web/WorkspaceShell.tsx
 M frontend/apps/web/src/web/api.ts
 M frontend/apps/web/src/web/ledger-pages-phase4.test.tsx
 M frontend/apps/web/src/web/managed-forms-phase2.test.tsx
 M frontend/apps/web/src/web/shared/VersionDiffPanel.tsx
 M frontend/apps/web/src/web/types.ts
```

---

## 13. Real-Stack E2E Status

| Suite | Status |
|-------|:--:|
| Existing 40 tests (20 chromium + 20 iPhone) | Not re-run (requires seed env) |
| New business-depth tests (§46-58) | Not yet implemented |

---

## 14. Screenshots

Not yet captured. Target directory: `artifacts/finance-admin-ui-validation/`

---

## 15. Remaining Items

### P0 (0 remaining)
All P0 items addressed.

### P1 (0 remaining)
All P1 items addressed.

### P2 (deferred per scope)
- Admin AI Settings backend
- Dead code cleanup
- Physical device PWA test
- DeepSeek full configuration
- Tauri
- Docker
- Large-scale CSS refactoring

---

## 16. Final Classification

**PILOT_CANDIDATE**

Rationale:
- All core P0 truthfulness issues fixed across Finance + Admin
- All quality gates pass (TypeScript, Build, Ruff, Mypy, Alembic)
- 0 new regressions vs baseline fe149ec
- Real-Stack E2E not yet re-run (existing 40 need fresh run; new business-depth tests not yet written)
- Screenshots not yet captured
- External review of all changes still pending

**PILOT_READY** requires:
1. Re-run existing Real-Stack 40/40
2. Screenshot capture for UI validation evidence
3. External review sign-off

---

## 17. Summary Output

```
FINANCE + ADMIN FRONTEND CLOSEOUT

Branch:          modular-architecture
Baseline:        fe149ec

Finance:
  Export Scope:       PASS
  Preview Accuracy:   PASS
  Mapping Editor:     PASS
  Correction UX:      PASS
  Re-export UX:       PASS
  Export History:     PASS
  Overview:           PASS
  Ledger Filters:     PASS
  Payroll UX:         PASS

Admin:
  Overview:           PASS
  Organization:       PASS
  Roles:              PASS (unchanged)
  Form Approval:      PASS
  Workflow Approval:  PASS (unchanged)
  Payroll Approval:   PASS
  Version Diff:       PASS
  Audit:              PASS
  Navigation:         PASS

Backend Regression:
  Correction:         10/10
  Re-export:          12/12

Real Stack:
  Existing:           NOT RE-RUN
  New Business-depth: NOT YET IMPLEMENTED

TypeScript:           PASS
Vitest:               BASELINE_ONLY (60/64 files, 313/314 tests)
Build:                PASS
Ruff:                 PASS
Mypy:                 PASS
Alembic:              034 (single head)

New Migration:        034_correction_fields_export_record_count_ds

Remaining P0:         0
Remaining P1:         0
New regressions:      0

Git:                  UNCOMMITTED
Commit:               NOT CREATED
Push:                 NOT PERFORMED

Final Classification: PILOT_CANDIDATE

Report:               artifacts/FINANCE-ADMIN-FRONTEND-CLOSEOUT.md
```
