# Production Governance Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent duplicate active cage workflows and show complete, permission-scoped upstream records inline.

**Architecture:** A persisted cage-occupancy row is acquired atomically with sorting creation and released in the linked form supervisor transaction. Record visibility is centralized in the bamboo facade; HTTP responses carry a read-only upstream projection consumed inline by the existing detail page.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, SQLite, React 18, TypeScript, Pytest, Vitest.

---

### Task 1: Persist cage occupancy

**Files:**
- Create: `alembic/versions/018_bamboo_cage_occupancy_ds.py`
- Modify: `app/adapters/database/models.py`
- Test: `tests/integration/test_migrations_backup_integrity_ds.py`

- [ ] **Step 1: Write the failing migration test** asserting upgrade to head creates `bamboo_cage_occupancies` and preserves existing rows.
- [ ] **Step 2: Run** `uv run pytest tests/integration/test_migrations_backup_integrity_ds.py -q`; expect failure because revision 018 does not exist.
- [ ] **Step 3: Add `BambooCageOccupancyRow`** with `occupancy_id`, `factory_id`, normalized/display cage numbers, sorting record, timestamps and release submission. Add a partial unique index on `(factory_id, cage_no_key)` where `released_at IS NULL`.
- [ ] **Step 4: Add revision 018** creating the table, foreign keys and partial unique index; do not infer active locks for historical completed data.
- [ ] **Step 5: Re-run the migration test**; expect PASS.
- [ ] **Step 6: Commit** `feat(bamboo): persist active cage occupancy`.

### Task 2: Acquire and release occupancy atomically

**Files:**
- Modify: `app/modules/bamboo_process/models_ds.py`
- Modify: `app/modules/bamboo_process/ports_ds.py`
- Modify: `app/modules/bamboo_process/errors_ds.py`
- Modify: `app/modules/bamboo_process/facade_ds.py`
- Modify: `app/adapters/database/bamboo_process_repository_ds.py`
- Test: `tests/modules/test_bamboo_process_facade_ds.py`
- Test: `tests/integration/test_bamboo_process_repository_ds.py`

- [ ] **Step 1: Write failing tests** for same-factory duplicate rejection, cross-factory reuse, concurrent uniqueness, persistence after restart, release only when the linked `DIPPING_DRYING` form receives `SUPERVISOR`, and reuse after release.
- [ ] **Step 2: Run** `uv run pytest tests/modules/test_bamboo_process_facade_ds.py tests/integration/test_bamboo_process_repository_ds.py -q`; expect duplicate tests to fail.
- [ ] **Step 3: Add domain contract:** normalized cage key is `strip().casefold()`, blank cages are rejected by existing validation, and `BambooCageOccupied` carries cage number and active sorting record ID.
- [ ] **Step 4: Replace sorting creation persistence** with `add_sorting_with_cage_occupancy(record, cage_no)` so record and lock commit in one transaction. On unique conflict, load the active occupancy and raise `BambooCageOccupied`.
- [ ] **Step 5: Release inside `_apply_stage_side_effects`** when `record.form_type is DIPPING_DRYING` and `submission.stage is SUPERVISOR`, keyed by `record.production_object_id`.
- [ ] **Step 6: Re-run targeted tests**; expect PASS.
- [ ] **Step 7: Commit** `feat(bamboo): enforce cage workflow exclusivity`.

### Task 3: Return stable API conflicts and scoped read-only records

**Files:**
- Modify: `app/modules/bamboo_process/state_machine_ds.py`
- Modify: `app/modules/bamboo_process/facade_ds.py`
- Modify: `app/api/schemas/bamboo_process_ds.py`
- Modify: `app/api/routers/mobile_bamboo_ds.py`
- Test: `tests/api/test_mobile_bamboo_ds.py`

- [ ] **Step 1: Write failing API tests** asserting duplicate creation returns HTTP 409 with `CAGE_ALREADY_IN_USE`, supervisors/managers/inspectors can read active same-factory upstream records, production roles cannot read unrelated records, and finance/admin can read cross-factory records.
- [ ] **Step 2: Run** `uv run pytest tests/api/test_mobile_bamboo_ds.py -q`; expect failures.
- [ ] **Step 3: Centralize visibility:** production roles retain workflow visibility; `INSPECTOR`, `SUPERVISOR`, and `PLANT_MANAGER` may read all records in their factory; `FINANCE_APPROVER` and `SYSTEM_ADMIN` may read across factories. Submission permissions remain unchanged.
- [ ] **Step 4: Add `upstream_record` response projection** containing source base data and effective submissions. Populate it server-side for linked records; never grant edit capability through this projection.
- [ ] **Step 5: Map `BambooCageOccupied`** to HTTP 409 with stable code, cage number and active record ID.
- [ ] **Step 6: Re-run API tests**; expect PASS.
- [ ] **Step 7: Commit** `feat(api): expose cage conflicts and upstream records`.

### Task 4: Embed upstream record inline

**Files:**
- Modify: `frontend/packages/api-client/src/mobile_ds.ts`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooRecordDetailPage.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooStageForm.tsx`
- Modify: `frontend/apps/web/src/styles.css`
- Test: `frontend/apps/web/src/mobile/v3/BambooV3Pages.test.tsx`

- [ ] **Step 1: Write failing component tests** asserting the linked form renders source base fields and submissions inline, has no upstream navigation link, and non-signing roles see a read-only banner rather than an empty page.
- [ ] **Step 2: Run** `npm.cmd run test -w @form-detection/web -- BambooV3Pages.test.tsx`; expect failure.
- [ ] **Step 3: Extend `BambooRecord`** with nullable `upstream_record` containing record identity, base info and submissions.
- [ ] **Step 4: Replace `SourceCard` navigation** with an accessible expandable read-only section. Reuse field/stage label formatters and do not render submit controls for view-only roles.
- [ ] **Step 5: Re-run the component test and TypeScript check**; expect PASS.
- [ ] **Step 6: Commit** `feat(mobile): embed read-only upstream workflow`.

### Task 5: Phase verification

**Files:**
- Modify: `PROGRESS.md`

- [ ] **Step 1: Run** `uv run pytest tests/modules/test_bamboo_process_facade_ds.py tests/integration/test_bamboo_process_repository_ds.py tests/api/test_mobile_bamboo_ds.py tests/integration/test_migrations_backup_integrity_ds.py -q`; expect PASS.
- [ ] **Step 2: Run** `uv run python -m ruff check app tests alembic/versions/018_bamboo_cage_occupancy_ds.py`; expect PASS.
- [ ] **Step 3: Run** `uv run python -m mypy app config`; expect PASS.
- [ ] **Step 4: Run** `npm.cmd run typecheck` and the targeted frontend test; expect PASS.
- [ ] **Step 5: Update `PROGRESS.md`** with migration, behavior, commands and results.
- [ ] **Step 6: Commit** `docs: record production governance phase 1 verification`.
