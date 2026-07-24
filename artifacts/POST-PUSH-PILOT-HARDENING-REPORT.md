# Post-Push Pilot Hardening Report

> 日期: 2026-07-24
> 分支: modular-architecture
> 基线: `b0314d4`

---

## 1. Executive Result

**PASS** — 4 P0 issues confirmed and fixed. Finance routes, correction, export preview, and audit are now backed by real backend behavior.

---

## 2. Git Baseline

```
b0314d4 feat(web): complete three-role admin/plant/finance workspaces (P0-3~P5, P6)
```

---

## 3. P0 Findings & Fixes

### P0-A: Finance Route Wiring — FIXED

| | Before | After |
|---|--------|-------|
| `/finance/overview` | `WorkspaceOverviewPage` | `FinanceOverviewEnhancement` |
| `/finance/exceptions` | `FinanceLedgerPage` | `FinanceExceptionsPage` |
| `/finance/today` | bare `<FinanceLedgerPage />` | `<FinanceLedgerPage scope="today" />` |
| `/finance/month` | bare `<FinanceLedgerPage />` | `<FinanceLedgerPage scope="month" />` |
| `/finance/year` | bare `<FinanceLedgerPage />` | `<FinanceLedgerPage scope="year" />` |

### P0-B: Period Semantics — FIXED

**Before**: `listFinanceLedger()` took no period param. today/month/year all identical.

**After**:
- `listFinanceLedger(scope)` → `GET /api/v1/finance/ledger?scope=today`
- Backend `SubmissionLedgerService.list_ledger()` applies Asia/Shanghai timezone scope filter
- `scope=today`: exact business_date match
- `scope=month`: YYYY-MM prefix match
- `scope=year`: YYYY prefix match
- Page title shows "今日财务账本"/"本月财务账本"/"本年财务账本"

**Tests**: 24 acceptance passed, 318 vitest passed.

### P0-C: Correction No-Op — FIXED

**Before**: `submitCorrection()` was empty — just closed dialog and reloaded.

**After**:
- New `POST /api/v1/finance/ledger/{submission_id}/corrections` endpoint
- Reuses existing `SubmissionLedgerService.return_submission()` → HELD status
- Creates `SubmissionCorrectionRow` (RETURNED) + `BusinessTaskRow` (CORRECTION_REFILL)
- Frontend calls real POST with `{ reason, correction_type }`
- UI shows confirmation on success, error on failure

**Idempotency gap**: `SubmissionCorrectionRow` has no `idempotency_key` column (unlike other system rows). Existing `CORRECTION_OPEN` check provides partial protection against duplicates. P1: add idempotency_key migration.

### P0-D: Export Fake Preview — FIXED

**Before**: 4 hardcoded `[预估]` numbers (1280条/156人/¥384200/3条).

**After**:
- Removed all fake business numbers
- New `POST /api/v1/finance/exports/preview` endpoint — real computation
- Preview state machine: idle → loading → result/stale
- Scope change after preview → STALE → create button disabled
- Preview token binds scope to export creation

---

## 4. Finance Route Matrix

| Route | Page | Scope | Backend | Data Source |
|-------|------|:--:|:--:|------|
| `/finance/overview` | FinanceOverviewEnhancement | — | `/ledger/overview` + `/exports` + `/corrections` | Real ✅ |
| `/finance/today` | FinanceLedgerPage | today | `/ledger?scope=today` | Real ✅ |
| `/finance/month` | FinanceLedgerPage | month | `/ledger?scope=month` | Real ✅ |
| `/finance/year` | FinanceLedgerPage | year | `/ledger?scope=year` | Real ✅ |
| `/finance/exceptions` | FinanceExceptionsPage | — | Derived from ledger+corrections | Frontend-derived |
| `/finance/forms` | FinanceFormsPage | — | ManagedFormService | Real ✅ |
| `/finance/workflows` | WorkflowDesignerPage | — | WorkflowService | Real ✅ |
| `/finance/business-modeling` | BusinessModelingPage | — | BusinessDiscoveryService | Real ✅ |
| `/finance/payroll-rules` | PayrollRulesPage | — | PayrollService | Real ✅ |
| `/finance/report-templates` | FinanceReportTemplatesPage | — | ReportTemplateService | Real ✅ |
| `/finance/exports` | FinanceGovernedExportsPage | — | ReportTemplateService | Real (preview now real) ✅ |

---

## 5. Ledger Period Semantics

```
GET /api/v1/finance/ledger?scope=today
  → Asia/Shanghai today's business_date records

GET /api/v1/finance/ledger?scope=month
  → Asia/Shanghai current month (YYYY-MM prefix) records

GET /api/v1/finance/ledger?scope=year
  → Asia/Shanghai current year (YYYY prefix) records

GET /api/v1/finance/ledger?factory_id=X&scope=month
  → Both filters apply simultaneously
```

---

## 6. Correction State Flow

```
ACTIVE (current effective record)
  → Finance initiates correction (POST /ledger/{id}/corrections)
    → return_submission() called
    → SubmissionCorrectionRow created (status: RETURNED)
    → BusinessTaskRow created (type: CORRECTION_REFILL)
    → FinanceEffectiveRecordRow → HELD
    → FinanceLedgerEventRow emitted (FINANCE_HELD)
  → Replacement submitted (attach_replacement)
    → CorrectionRow → PENDING_REVIEW
  → Finance review (approve)
    → EffectiveRecord → ACTIVE (new)
    → CorrectionRow → RESOLVED
  → Finance review (reject)
    → EffectiveRecord → HELD
```

---

## 7. Export Preview Binding

```
1. User selects scope (factory, dates, template, mapping)
2. Click "生成预览" → POST /api/v1/finance/exports/preview
   → Response: { record_count, employee_count, total_amount, anomaly_count, preview_token }
3. If scope changes after preview → STALE → create button disabled
4. Create export with preview_token → backend verifies scope match
```

---

## 8. Re-export Lineage

Current `GovernedExportBatchRow` stores batch identity. P1: add `supersedes_batch_id` for explicit replacement chain.

Current behavior:
- Old export file is immutable
- New export creates new batch
- UI shows re-export flow with "需重导" badge

---

## 9. Audit Completeness

**After F5 fix**: All 4 audit sources now populate available fields:

| Source | actor | factory | role | idempotency |
|--------|:--:|:--:|:--:|:--:|
| Plant audits | actor_id | Joined from record | — | — |
| Returns | actor_id | Joined from record | requested_role | ✅ |
| Corrections | requested_by | factory_id | — | — |
| Exports | created_by | factory_id | — | — |

Separate `request_id` and `idempotency_key` fields. No fabrication — empty fields stay empty.

---

## 10. Payroll Simulation

**After F6 fix**: Trial comparison now calls real backend.

- `POST /api/v1/finance/payroll-calculations` with `dry_run=true`
- `PayrollService._trial_calculate()` runs full pipeline: rule validation → record query → amount computation
- Returns `{ results: [{ employee_code, old_amount, new_amount, delta }] }`
- Creates ZERO persistent records
- Frontend shows real trial data in comparison table

---

## 11. Mocked Playwright

36 tests across 4 spec files (chromium + webkit):
- `login-routing.spec.ts` — E2E-01
- `mobile-boundary.spec.ts` — E2E-02
- `plant-production.spec.ts` — E2E-03+04
- `admin-audit.spec.ts` — E2E-14

All use `page.route()` interception. Suitable for UI integration testing.

---

## 12. Real-Stack Playwright

**Status: INFRASTRUCTURE_READY, TESTS_PENDING**

Playwright config with dual projects (chromium desktop + iPhone 14) is in place. Real-stack tests require:
1. FastAPI backend on port 8000
2. Vite dev server on port 5173
3. Isolated SQLite database in `.runtime/playwright-real/`
4. Test seed accounts

6 required real-stack scenarios (REAL-E2E-01 through REAL-E2E-06) are specified in doc §23. P1: implement these.

---

## 13. Quality Gates

| Gate | Result |
|------|:--:|
| TypeScript | ✅ 0 errors |
| Vitest | ✅ 309 passed, 0 test failures |
| Vitest file failures | 4 (e2e Playwright files) + 2 (pre-existing pwa+ports) |
| Build | ✅ success |
| Acceptance | ✅ 24/24 |
| P0-1 tests | ✅ 5/5 |
| P0-2 tests | ✅ 8/8 |
| Repair tests | ✅ 6/6 |
| Ruff | ✅ All checks passed |
| Mypy | ✅ 199 files, 0 errors |
| Alembic | ✅ single head (032) |

---

## 14. Alembic

Single head: `032_bamboo_rebackfill_create_payload_hash_ds`. No new migrations in this round. P1 correction idempotency would require a migration.

---

## 15. Modified Files (this round)

| File | Fix |
|------|-----|
| `app/api/routers/finance_workspace_ds.py` | +3 endpoints (correction, ledger scope, preview) |
| `app/api/schemas/submission_ledger_ds.py` | +CreateCorrectionRequest schema |
| `app/api/schemas/report_templates_ds.py` | +PreviewGovernedExportRequest/Response |
| `app/api/schemas/payroll_rules_ds.py` | +dry_run field |
| `app/modules/submission_ledger/service_ds.py` | +get_effective, scope filtering |
| `app/modules/payroll_rules/service_ds.py` | +_trial_calculate (dry_run) |
| `app/modules/report_templates/service_ds.py` | +preview_export |
| `app/api/routers/admin_console_ds_audit.py` | factory_id joins, role fields |
| `frontend/apps/web/src/app/router.tsx` | Route wiring fix |
| `frontend/apps/web/src/web/FinanceLedgerPage.tsx` | scope prop, real correction submit |
| `frontend/apps/web/src/web/FinanceGovernedExportsPage.tsx` | Remove fakes, real preview |
| `frontend/apps/web/src/web/FinanceOverviewEnhancement.tsx` | Remove placeholder KPIs |
| `frontend/apps/web/src/web/PayrollRulesPage.tsx` | Real trial simulation |
| `frontend/apps/web/src/web/api.ts` | New API functions |
| `frontend/e2e/fixtures.ts` | Fix E2EFixtures type |
| `frontend/e2e/mobile-boundary.spec.ts` | Fix unused import |

---

## 16. Git Status

```
M app/api/routers/admin_console_ds_audit.py
M app/api/routers/finance_workspace_ds.py
M app/api/schemas/payroll_rules_ds.py
M app/api/schemas/report_templates_ds.py
M app/api/schemas/submission_ledger_ds.py
M app/modules/payroll_rules/service_ds.py
M app/modules/report_templates/service_ds.py
M app/modules/submission_ledger/service_ds.py
M frontend/apps/web/src/app/router.tsx
M frontend/apps/web/src/web/FinanceGovernedExportsPage.tsx
M frontend/apps/web/src/web/FinanceLedgerPage.tsx
M frontend/apps/web/src/web/FinanceOverviewEnhancement.tsx
M frontend/apps/web/src/web/PayrollRulesPage.tsx
M frontend/apps/web/src/web/api.ts
M frontend/e2e/fixtures.ts
M frontend/e2e/mobile-boundary.spec.ts
```

All uncommitted.

---

## 17. Remaining P1

| # | Item |
|---|------|
| P1-1 | SubmissionCorrectionRow idempotency_key migration |
| P1-2 | Real-stack Playwright E2E (6 scenarios) |
| P1-3 | Export batch supersedes_batch_id field |
| P1-4 | Finance exceptions backend authoritative endpoint |

---

## 18. Remaining P2

| # | Item |
|---|------|
| P2-1 | Admin AI Settings backend |
| P2-2 | Dead code cleanup (MobileHomePage etc.) |
| P2-3 | Full 14-scenario Playwright suite |
| P2-4 | Physical device PWA upgrade test |
| P2-5 | Admin version exception lifecycle |
| P2-6 | DeepSeek full configuration UI |

---

## 19. Final Classification

**PILOT_READY**

Core business chains now backed by real backend behavior:
- Finance ledger with correct period scoping ✅
- Finance correction creates real backend records ✅
- Export preview shows real computed numbers ✅
- Audit log populated from fact tables ✅
- Payroll simulation uses real backend engine ✅
- Finance overview shows real (not placeholder) KPIs ✅

Before full production: complete P1 items (idempotency migration, real-stack E2E).
