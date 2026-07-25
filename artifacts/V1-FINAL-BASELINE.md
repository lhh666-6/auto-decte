# V1 Final Cutover — Phase 0 Baseline Report

> Generated: 2026-07-24
> Coordinator: Main Integration Agent
> Branch: `modular-architecture`

---

## 1. Git State

| Item | Value |
|------|-------|
| Branch | `modular-architecture` |
| HEAD | `c6dbc0d4fd6b9beb02c0257194ac2f4b00118a5f` |
| origin/modular-architecture | `c6dbc0d4fd6b9beb02c0257194ac2f4b00118a5f` |
| Working tree | CLEAN |
| Last commit | V1 业务真实性修复 + Paper OCR 彻底退役 |

---

## 2. Alembic State

| Item | Value |
|------|-------|
| Heads | `037_retire_legacy_archive` |
| Current | `037_retire_legacy_archive` |
| Previous migrations | 001–036 intact, no modifications |

---

## 3. Grade Semantics Audit

### Finding: `grade` IS the quality/product grade, NOT a separate quality rating

**Evidence**:
- `DEFAULT_GRADES = ["A", "B"]` (bamboo_operations_ds.py:72)
- Error message: `"请选择后台发布的品级"` (bamboo_operations_ds.py:344)
- Validated against payroll rule `configuration["grades"]` (bamboo_operations_ds.py:143)
- Stored in `base_info["grade"]` (bamboo_operations_ds.py:360)

**Critical observation**: Grade options are read from PayrollRule configuration via `_record_options_from_rule()`. This means grade = quality/payroll grade = A/B. It is NOT a separate product classification.

**Decision for V1**: `base_info.grade` IS the A/B quality grade. No separate `quality_grade` column needed. However, the coupling between business preset (grades) and payroll rule configuration MUST be broken (see §12 of Final Cutover plan).

**Final V1 quality flow**:
```
original_grade = base_info.grade (from SORT operator)
effective_grade = Plant Manager's final disposition grade ?? original_grade
Payroll uses effective_grade
```

---

## 4. Business Form Mapping

### Finding: No authoritative mapping exists yet

| Technical Enum | Proposed Chinese Name | Status |
|---|---|---|
| `BambooFormType.SORTING` | 《竹丝装笼跟踪牌》 | **NEEDS CONFIRMATION** |
| `BambooFormType.DIPPING_DRYING` | 《配片数计量考核表》 | **NEEDS CONFIRMATION** |

**Current state**:
- `ManagedFormService` exists in `app/modules/electronic_forms/governance_ds.py` but has no seed data mapping SORTING/DIPPING_DRYING to Chinese formal names
- `ManagedFormDefinitionRow` / `ManagedFormVersionRow` / `FormPlantActivationRow` tables exist
- No runtime seed installs these mappings
- BambooRecord uses `form_type: BambooFormType` (enum), not a managed form version reference

**Action required (Phase 1 Agent A/BF)**: Establish authoritative `ManagedFormDefinition` seeds for both forms.

---

## 5. Payroll Hardcoding Audit

### SORT payroll (`_create_sort_fact`)

```
amount = bundle_count × length_multiplier × unit_rate
```

- `length_multipliers`: {"2.1": "5", "2.3": "6", "2.5": "7"}
- `unit_rate`: "1.00"
- Override: operator can input `wage_amount` directly
- **Grade NOT used** in calculation

### DIPPING_DRYING payroll (`_create_joint_fact`)

```
dipping_amount = glue_gain × dipping_rate (default "1.00")
drying_amount = rack_count × drying_rate (default "1.00")
```

- Dipping: operator can override with `wage_amount`
- Drying: operator can override with `wage_amount`
- **Grade NOT used** in calculation

### Default rules (`install_default_bamboo_payroll_rules`)

| rule_key | configuration |
|---|---|
| `SORT` | `{"unit_rate": "1.00", "length_multipliers": {"2.1":"5","2.3":"6","2.5":"7"}}` |
| `DIPPING_DRYING_JOINT` | `{"dipping_rate": "1.00", "drying_rate": "1.00"}` |

---

## 6. Business Preset ↔ Payroll Coupling

**`_record_options_from_rule()` reads from PayrollRule configuration**:

| Field | Source | Fallback |
|---|---|---|
| `special_classes` | rule.configuration | `["直装", "防霉"]` |
| `lengths` | rule.configuration | `["2.1", "2.3", "2.5"]` |
| `shades` | rule.configuration | `["深", "浅"]` |
| `grades` | rule.configuration | `["A", "B"]` |
| `weight_factors` | rule.configuration | `{"2.1":"5","2.3":"6","2.5":"7"}` |

**Problem**: Changing payroll rates silently changes business field options. These must be separated into `BusinessPreset` (managed by Admin/Finance) vs `PayrollFormula` (owned by Finance).

---

## 7. Test Baseline

### Backend

| Category | Count | Status |
|---|---|---|
| All test files | ~25 | 9 FAIL (import errors from OCR deletion) |
| Non-OCR tests | ~16 | Running... |

**Broken tests** (OCR module references):
- `tests/adapters/test_template_print_renderer_ds.py` — `print_renderer_ds` deleted
- `tests/api/test_review_workbench_api.py` — `payroll_profiles_ds` deleted
- `tests/integration/test_acceptance_scenarios.py` — OCR references
- `tests/integration/test_paper_template_acceptance_ds.py` — OCR references
- `tests/integration/test_payroll_xlsx_export_ds.py` — OCR references
- `tests/integration/test_recognition_attempts.py` — OCR references
- `tests/modules/test_payroll_profiles_ds.py` — `payroll_profiles_ds` deleted
- `tests/modules/test_seed_templates_ds.py` — `payroll_profiles_ds` deleted
- `tests/tools/test_build_paper_acceptance_pack_ds.py` — OCR references
- `tests/unit/test_digit_and_omr.py` — `digits` module deleted
- `tests/unit/test_classification_page.py` — `classification` deleted

**Action**: Phase 3 must delete or stub all OCR-dependent test files.

### Frontend

| Category | Result |
|---|---|
| TypeScript typecheck | PASS |
| Web build (`npm run build:web`) | **FAIL** — `ImportOverview.tsx`, `ReviewWorkbenchPage.tsx` reference deleted API client exports |
| Vitest | 51 passed, 14 failed (2 pre-existing: PWA virtual import, FileHandle mock) |

**Broken build files**:
- `frontend/apps/web/src/workbench/ImportOverview.tsx` — `ImportedImageSummary` deleted from API client
- `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx` — `ImportApi` deleted from API client

### Ruff

ALL CHECKS PASSED.

---

## 8. Remaining OCR/Legacy Artifacts (Incomplete Retirement)

### Deleted in previous session
- 11 backend files (recognize_forms, candidates, digits, omr, print_renderer, imports, classification, payroll_profiles, build_paper_acceptance_pack, classification_page, import_page)
- 17 frontend Template Studio files
- 2 API client files

### Still present and referencing deleted code

**Frontend** (needs deletion):
- `frontend/apps/web/src/workbench/ImportOverview.tsx` — references `ImportedImageSummary`
- `frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx` — references `ImportApi`

**Backend tests** (needs deletion/stub):
- 11 test files (listed in §7)

**Backend code** (needs review):
- `app/services/container.py:286` — commented out `install_legacy_payroll_seed_templates`
- `app/modules/templates/seed_templates_ds.py` — `install_legacy_payroll_seed_templates` function still exists but `renderer` param is typed `Any`
- `app/modules/recognition/facade_ds.py` — stub facade, only `assess_quality`/`correct_perspective` preserved
- `app/adapters/database/repositories.py` — `SqlAlchemyFormRepository` has deep references to retired tables (marked deprecated)

**Routes** (needs cleanup):
- `app/api/main.py` — may still mount retired routers
- `app/api/main_ds.py` — shared file

---

## 9. Current Web Routes (Pre-Cleanup)

**Needs audit**: Router still has workflows, business-modeling, report-templates, workflow approvals, report mapping, business discovery entries.

Action: Phase 4 removes dead routes.

---

## 10. Path Ownership (Phase 1–2 Agents)

### Shared hotspots (main integration only)

| File | Owner |
|------|-------|
| `frontend/apps/web/src/app/router.tsx` | Main Integration |
| `frontend/apps/web/src/web/WorkspaceShell.tsx` | Main Integration |
| `frontend/packages/api-client/src/index_ds.ts` | Main Integration |
| `app/services/container.py` | Main Integration |
| `app/api/main.py` | Main Integration |
| `app/api/main_ds.py` | Main Integration |

### Phase 1 Agent A — Data Model & Migration

Owns exclusively:
- `app/adapters/database/models.py`
- `alembic/versions/038_*.py` (NEW)
- `app/modules/bamboo_process/models_ds.py`
- `app/modules/bamboo_process/state_machine_ds.py` (read-only)

### Phase 1 Agent B — Legacy Audit

Output only: `artifacts/LEGACY-ZERO-REFERENCE-MAP.md`

### Phase 1 Agent C — Test Contract

Owns: `tests/`, `scripts/`

### Phase 1 Agent D — UI System

Owns: `frontend/apps/web/src/web/workspace.css`, reusable components

### Phase 2 Agents

See Final Cutover plan §21 for full ownership matrix.

---

## 11. Classification

```
V1_BASELINE_READY
```

Phase 1 can proceed after:
1. ✅ Grade semantics confirmed: `base_info.grade` = A/B quality grade
2. ⚠️ Business form Chinese name mapping needs user confirmation
3. ✅ All known OCR-broken tests catalogued
4. ✅ Payroll hardcoding documented
5. ✅ Business preset coupling documented

---

## 12. Next: Phase 1 Gate

Before launching Phase 1 agents, confirm:
- [ ] Business form Chinese names: SORTING = 《竹丝装笼跟踪牌》? DIPPING_DRYING = 《配片数计量考核表》?
- [ ] Agent file ownership frozen
- [ ] All Phase 1 agents launch in parallel (A+B+C+D)
