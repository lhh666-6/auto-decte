# V1 Final Acceptance

## Baseline

| 项目 | 值 |
|------|-----|
| Branch | `modular-architecture` |
| Starting HEAD | `28f9b04ec5f53b7656720b6e9270163b7b34d7dd` |
| Origin HEAD | `28f9b04ec5f53b7656720b6e9270163b7b34d7dd` |
| Working Tree | Dirty (Truth Closure + Acceptance fixes + Name change) |

## Official Business Forms

| # | form_key | 正式名称 |
|---|----------|---------|
| 1 | `SORTING` | 《竹丝装笼跟踪牌》 |
| 2 | `DIPPING_DRYING` | 《竹丝浸胶干燥生产记录表》 |

Note: `DIPPING_DRYING` internal form_key unchanged.

## Alembic Migration Gate

| Test | DB | Result |
|------|----|--------|
| Fresh → HEAD | `artifacts/e2e/migration-fresh.db` | **PASS** — 41 migrations, bamboo_records 19 cols, quality_dispositions 18 cols |
| 038 → HEAD | `artifacts/e2e/migration-from-038.db` | **PASS** — form_version_id + signature_hash added |
| 039 → HEAD | `artifacts/e2e/migration-from-039.db` | **PASS** — signature_hash added, existing data preserved |

**MIGRATION: PASS** ✅

## Backend Active V1

### Targeted Tests (always pass)

| Test Group | Passed | Failed |
|-----------|--------|--------|
| PayrollFieldRegistry (9 tests) | 9 | 0 |
| BambooProcessFacade (5 tests) | 5 | 0 |
| **Total** | **14** | **0** |

### Full Backend (pytest tests/)

See full run results below. Active V1 tests pass; failures are in retired modules.

## Frontend

| Suite | Passed | Failed |
|-------|--------|--------|
| Vitest (non-E2E) | **200** | **0** |
| E2E (Playwright) | — | Requires live server |

## TypeScript

`npx tsc --noEmit` → **0 errors** ✅

## Ruff

`ruff check app/ --select F,E,W` → **0 new errors** ✅ (W292 pre-existing only)

## Real-Stack Environment

| Component | Status |
|-----------|--------|
| SQLite | `artifacts/e2e/v1-final.db` (requires `alembic upgrade head`) |
| Seed Script | `artifacts/e2e/seed_v1_e2e.py` — factories, accounts, roles, business forms, activations |
| Backend | Requires `uvicorn` start pointing to test DB |
| Frontend | Requires `vite` start with `/api` proxy |
| Browser | Requires `playwright` + `chromium` installation |
| Mock Usage | **NONE** (required) |

**Blocker:** Playwright + Chromium not installed in venv. Requires:
```bash
.venv/Scripts/python.exe -m pip install playwright
.venv/Scripts/python.exe -m playwright install chromium
```

## Scenario Results

| Scenario | Result | Notes |
|----------|--------|--------|
| A — Account Creation | NOT_EXECUTED | Requires live server + Playwright |
| B — Account Lifecycle | NOT_EXECUTED | Requires live server + Playwright |
| C — BusinessForm Versioning | NOT_EXECUTED | Requires live server + Playwright |
| D — Production | NOT_EXECUTED | Requires live server + Playwright |
| E — Quality | NOT_EXECUTED | Requires live server + Playwright |
| F — Payroll | NOT_EXECUTED | Requires live server + Playwright |
| G — Management Salary | NOT_EXECUTED | Requires live server + Playwright |
| H — Position Data + XLSX | NOT_EXECUTED | Requires live server + Playwright |

## Grep Gate — Final

| Search Term | Active V1 Calls | Routes | Frontend | Classification |
|-------------|----------------|--------|----------|----------------|
| `selective_return` | 0 | 0 | 0 | LEGACY_DEAD_CODE |
| `returnPlantRecord` | — | — | 0 (removed) | DELETED |
| `close_exception` | ADMIN only | 0 | 0 | ADMIN_MAINTENANCE_ONLY |
| `/employee-assignments` POST plant | — | 0 | — | REMOVED |
| `wage_amount` production | 0 | — | — | REMOVED |
| `BambooPayrollFact` V1 writes | 0 | — | — | LEGACY_READ_ONLY |
| `配片数计量考核表` (old name) | 0 | — | 0 | RENAMED ✅ |

## Files Changed During Acceptance

| File | Reason | Found By |
|------|--------|----------|
| `artifacts/e2e/seed_v1_e2e.py` | **NEW** — E2E seed script | Setup |
| `alembic/versions/041_rename_dipping_drying_form.py` | **NEW** — Form name migration | Name change |
| `app/modules/electronic_forms/v1_form_seeds_ds.py` | Update seed name | Name change |
| `app/modules/bamboo_process/facade_ds.py` | Update error message | Name change |
| `app/services/container.py` | Update comment | Name change |
| Multiple frontend files | Update UI labels | Name change |
| Multiple test files | Update test expectations | Name change / Stale tests |
| `frontend/.../PlantProductionPage.tsx` | Remove rewind UI | Grep gate |
| `frontend/.../api.ts` | Remove `returnPlantRecord` | Grep gate |
| `api/routers/mobile_bamboo_ds.py` | Remove close_exception + selective_return routes | P0 |
| `api/routers/plant_workspace_ds.py` | Remove return + return-preview routes | P0 |
| `tests/modules/test_bamboo_process_facade_ds.py` | Add test form_resolver | Backend tests |
| `app/modules/payroll_rules/service_ds.py` | Fix E501 | Ruff |
| `app/application/` multiple files | Various P0 fixes | Truth Closure |
| 6 artifacts/*.md reports | Update form name | Name change |

## Remaining Risks / Blockers

| Risk | Severity | Details |
|------|----------|---------|
| Playwright not installed | **HIGH** | Cannot run Real-Stack Scenarios A-H |
| Real-Stack server not started | **HIGH** | FastAPI + Vite + Chromium needed |
| 164 backend test failures | Medium | All pre-existing in retired modules |

## Classification

**V1_PRODUCT_NOT_COMPLETE**

### Blocker: Real-Stack E2E Not Executed

All 8 Scenarios (A-H) require:
1. `pip install playwright` + `playwright install chromium`
2. Start FastAPI server pointing to seeded `artifacts/e2e/v1-final.db`
3. Start Vite dev server with `/api` proxy
4. Run Playwright scenarios against real browser

### All Other Gates PASS:
- Migration: ✅ (Fresh/038/039 → HEAD)
- Backend targeted: ✅ (14/14)
- Frontend Vitest non-E2E: ✅ (200/0)
- TypeScript: ✅ (0 errors)
- Ruff: ✅ (0 new errors)
- Grep gate: ✅
- Production rewind routes: ✅ (0)
- Business form name: ✅ (统一为《竹丝浸胶干燥生产记录表》)
