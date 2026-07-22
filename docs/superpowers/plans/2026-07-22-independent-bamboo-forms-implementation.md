# Independent Bamboo Forms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single serial bamboo record with independently audited sorting and dipping-drying forms while preserving V3 mobile interactions and finance traceability.

**Architecture:** A bamboo record becomes one independent form identified by `form_type`. Workflow order is selected from a form-definition registry; a signed sorting form automatically releases a linked dipping-drying form with a versioned source snapshot. Each record independently reaches supervisor review, plant audit, payroll effectiveness, and finance approval.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, Alembic, React 18, TypeScript, Vitest, pytest.

**Execution constraint:** Reuse the current `modular-architecture` branch, database environment, Node modules, Python environment, and ports. Do not create another worktree or reinstall dependencies. Per the user's instruction, complete implementation before running the consolidated test suite.

---

### Task 1: Add independent form workflow metadata

**Files:**
- Modify: `app/modules/bamboo_process/models_ds.py`
- Modify: `app/modules/bamboo_process/state_machine_ds.py`
- Modify: `app/modules/bamboo_process/ports_ds.py`
- Modify: `app/modules/bamboo_process/facade_ds.py`

- [ ] Add `BambooFormType` with `SORTING` and `DIPPING_DRYING`, and add `form_type`, `production_object_id`, `source_record_id`, and `source_snapshot` to `BambooRecord`.
- [ ] Replace the global stage order with a form definition registry:

```python
FORM_STAGE_ORDER = {
    BambooFormType.SORTING: (
        BambooStage.SORT,
        BambooStage.SUPERVISOR,
        BambooStage.PLANT_AUDIT,
    ),
    BambooFormType.DIPPING_DRYING: (
        BambooStage.DIPPING,
        BambooStage.DRYING,
        BambooStage.SUPERVISOR,
        BambooStage.PLANT_AUDIT,
    ),
}
```

- [ ] Make `next_stage`, visibility, current-role checks, and completion calculations accept the record form type.
- [ ] Make the completed task bucket mean “the current role has a valid submission on this independent form”, while waiting means that role has submitted but this form continues through its own review.
- [ ] After the first valid `SORT` submission, create exactly one linked `DIPPING_DRYING` record whose first stage is `DIPPING`, whose `production_object_id` matches the sorting form, and whose source snapshot records the sorting form ID, display number, revision, and copied base fields.

### Task 2: Persist form types and source links

**Files:**
- Create: `alembic/versions/017_bamboo_independent_forms_ds.py`
- Modify: `app/infrastructure/database/migrations.py`
- Modify: `app/adapters/database/models.py`
- Modify: `app/adapters/database/bamboo_process_repository_ds.py`

- [ ] Add columns to `bamboo_records`:

```text
form_type VARCHAR NOT NULL DEFAULT 'SORTING'
production_object_id VARCHAR
source_record_id VARCHAR REFERENCES bamboo_records(record_id)
source_snapshot JSON NOT NULL DEFAULT '{}'
```

- [ ] Backfill existing rows as `SORTING`, set missing `production_object_id` to `record_id`, add an index for source lookup, and advance `HEAD_REVISION` to `017`.
- [ ] Extend auto-created legacy database compatibility with the same columns and backfill so the existing demonstration database remains usable.
- [ ] Map all new fields in `_record_row` and `_record`, and add `find_linked(form_type, source_record_id)` to the repository port and SQL implementation.
- [ ] Scope payroll fact creation by form type: sorting records create only sort facts; dipping-drying records create only joint facts. Plant audit activates only facts belonging to the audited independent form.

### Task 3: Expose independent forms through the mobile API

**Files:**
- Modify: `app/api/schemas/bamboo_process_ds.py`
- Modify: `app/api/routers/mobile_bamboo_ds.py`
- Modify: `app/application/bamboo_operations_ds.py`
- Modify: `frontend/packages/api-client/src/mobile_ds.ts`

- [ ] Add form metadata and source snapshot to record response contracts.
- [ ] Normalize sorting modes to exactly `分选` and `分选+装笼`; reject the obsolete standalone `装笼` value.
- [ ] Validate production fields by stage: moisture for all production steps, dipping weights, and unique drying rack numbers.
- [ ] Keep finance APIs unchanged externally; because each form has its own record and payroll facts, existing daily/monthly export and inquiry endpoints naturally trace each wage entry to one effective form.
- [ ] Update TypeScript types so mobile pages can render form-specific flows and source links without string guesses.

### Task 4: Align the mobile UI with V3 interactions

**Files:**
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooTaskListPage.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooStageForm.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooRecordDetailPage.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx`
- Modify: `frontend/apps/web/src/mobile/mobile.css`

- [ ] Change the new-work mode buttons to `分选` and `分选+装笼`.
- [ ] Include the V3 moisture-point interaction in the initial sorting sheet. The final confirmation must create the sorting form and submit/sign `SORT` in one user action.
- [ ] After submission, show the sorting form as the worker's completed step with the form state “待主管审核”; do not label it “等待浸胶”.
- [ ] Render a form-specific progress strip:

```text
分选表: 分选签字 → 主管审核 → 厂长审核 → 已生效
联合表: 浸胶记录 → 干燥联合签字 → 主管审核 → 厂长审核 → 已生效
```

- [ ] Render the linked source card on the dipping-drying form with source form number, version, and reused fields.
- [ ] Replace generic free-form production fields with V3 fields, picker/number interactions, server-derived identity/time, confirm sheet, and clear online-signature behavior.
- [ ] Preserve real role assignment; do not add the prototype's role selector. Keep finance routed to the web interface.

### Task 5: Complete regression coverage and consolidated verification

**Files:**
- Modify: `tests/modules/test_bamboo_process_state_machine_ds.py`
- Modify: `tests/modules/test_bamboo_process_facade_ds.py`
- Modify: `tests/integration/test_bamboo_process_repository_ds.py`
- Modify: `tests/api/test_mobile_bamboo_ds.py`
- Modify: `tests/api/test_mobile_bamboo_operations_ds.py`
- Modify: `frontend/apps/web/src/mobile/v3/BambooV3Pages.test.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/bamboo.test.tsx`

- [ ] Cover the independent sorting workflow, automatic linked form creation, separate audits, completed-bucket semantics, source snapshot, mode validation, payroll isolation, and selective return behavior.
- [ ] Cover V3 mode selection, moisture validation, one-action sorting submission, form-specific status strip, and linked source rendering.
- [ ] Run Python checks:

```powershell
uv run python -m ruff check app tests
uv run python -m mypy app config
uv run python -m pytest tests/modules/test_bamboo_process_state_machine_ds.py tests/modules/test_bamboo_process_facade_ds.py tests/integration/test_bamboo_process_repository_ds.py tests/api/test_mobile_bamboo_ds.py tests/api/test_mobile_bamboo_operations_ds.py
```

- [ ] Run frontend checks:

```powershell
npm run typecheck
npm test -w apps/web -- --run src/mobile/v3/BambooV3Pages.test.tsx src/mobile/bamboo/bamboo.test.tsx
npm run build:web
```

- [ ] Upgrade the existing development database to revision `017`, restart the existing backend and Vite processes on their established ports, verify the mobile login and form workflow over LAN, then stop only temporary verification processes.
