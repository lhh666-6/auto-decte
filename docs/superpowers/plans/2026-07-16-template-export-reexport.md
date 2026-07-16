# Template Export and Re-export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a template-driven XLSX export center with preview, persistent tasks, immutable traceable batches, authorized downloads, formula-injection protection, and explicit re-export replacement.

**Architecture:** Keep reporting as the single export boundary, reuse the existing task state machine/SSE transport, and add an export-specific Router and Handler. Generate files through a mapping snapshot into a temporary path, persist the successful immutable batch and form status changes transactionally, then publish the final file without exposing its internal path.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, SQLite/Alembic, openpyxl, pytest, React 18, TypeScript, Vitest, Vite.

---

### Task 1: Export preview and mapping domain

**Files:**
- Create: `app/modules/reporting/models_ds.py`
- Modify: `app/application/export_forms.py`
- Modify: `app/modules/reporting/facade_ds.py`
- Test: `tests/integration/test_xlsx_export.py`

- [ ] **Step 1: Write failing preview tests**

Add tests that construct a published template with `ExportTarget("企业工资记录.xlsx", "计时考核单", "employee_id")`, then assert preview includes only a confirmed current record and returns explicit exclusions for an unconfirmed record or missing template mapping.

```python
preview = reporting.preview(FormFilters(), actor_id="finance")
assert [(item.form_id, item.record_version) for item in preview.included] == [("FORM-1", 1)]
assert preview.excluded[0].reasons[0].code == "NOT_CONFIRMED"
assert preview.mapping_snapshot[0].business_column == "employee_id"
```

- [ ] **Step 2: Verify RED**

Run: `uv run python -m pytest tests/integration/test_xlsx_export.py -q`

Expected: fail because `ReportingFacade.preview` and preview models do not exist.

- [ ] **Step 3: Implement preview value objects and final validation**

Create immutable `ExportMapping`, `ExportExclusionReason`, `ExportPreviewItem`, and `ExportPreview` dataclasses. Resolve every form's immutable template version through `SqlAlchemyTemplateRepository`, derive mappings from `field.export_target`, and keep preview read-only.

- [ ] **Step 4: Verify GREEN**

Run the same test command and expect all export integration tests to pass.

### Task 2: Template-driven XLSX and formula safety

**Files:**
- Modify: `app/adapters/export/xlsx.py`
- Modify: `app/application/export_forms.py`
- Test: `tests/integration/test_xlsx_export.py`

- [ ] **Step 1: Write failing workbook tests**

Assert template worksheet/business columns are used and the trace columns remain present. Parameterize hostile text values:

```python
@pytest.mark.parametrize("value", ["=1+1", "+SUM(A1:A2)", "-2+3", "@cmd", "\ufeff=hidden"])
def test_xlsx_escapes_formula_like_business_text(value: str, tmp_path: Path) -> None:
    assert exported_cell(value, tmp_path).value == "'" + value.lstrip("\ufeff")
```

- [ ] **Step 2: Verify RED**

Run the parameterized test and confirm openpyxl currently reads the unescaped value/formula.

- [ ] **Step 3: Implement mapping-driven writer**

Change `XlsxExporter.write` to accept the immutable mapping snapshot and group business columns by worksheet. Add a single `_safe_cell_value` function that prefixes dangerous strings but preserves numbers, booleans, dates, and `None`.

- [ ] **Step 4: Verify GREEN and legacy compatibility**

Run `uv run python -m pytest tests/integration/test_xlsx_export.py -q` and retain the four-sheet legacy test through a compatibility mapping.

### Task 3: Immutable export batch persistence and migration 007

**Files:**
- Create: `alembic/versions/007_export_batches_ds.py`
- Modify: `app/domain/models.py`
- Modify: `app/adapters/database/models.py`
- Modify: `app/adapters/database/repositories.py`
- Test: `tests/infrastructure/test_export_batches_migration_ds.py`
- Test: `tests/integration/test_xlsx_export.py`

- [ ] **Step 1: Write failing persistence tests**

Persist and reload a batch with template, mapping and filter snapshots, download name, included records and `supersedes_batch_id`; assert the old batch remains queryable after adding its replacement.

- [ ] **Step 2: Verify RED**

Run the two test files and confirm failures are missing columns/repository methods.

- [ ] **Step 3: Add migration and repository methods**

Append revision `007_export_batches_ds`, add JSON snapshot columns and `download_name`, and implement `get_export_batch` plus newest-first `list_export_batches`. Do not edit revisions `001`–`006`.

- [ ] **Step 4: Verify GREEN and migration compatibility**

Run the targeted tests plus `tests/infrastructure/test_migrations_backup_integrity_ds.py`.

### Task 4: Atomic export handler and task progress

**Files:**
- Create: `app/modules/reporting/handler_ds.py`
- Modify: `app/application/export_forms.py`
- Modify: `app/modules/tasks/service_ds.py`
- Modify: `app/services/container.py`
- Test: `tests/modules/test_reporting_handler_ds.py`

- [ ] **Step 1: Write failing Handler tests**

Cover successful progress, no eligible records, writer failure, database failure, temporary-file cleanup, final-file cleanup, and re-export replacement.

```python
task = tasks.submit(TaskCommand("XLSX_EXPORT", "EXPORTS", "finance", "key-1", payload))
handler.handle(task.task_id)
assert tasks.get(task.task_id).status is TaskStatus.SUCCEEDED
assert repository.get_export_batch_by_task(task.task_id) is not None
```

- [ ] **Step 2: Verify RED**

Run `uv run python -m pytest tests/modules/test_reporting_handler_ds.py -q` and confirm the Handler is missing.

- [ ] **Step 3: Implement synchronous production Handler boundary**

The Handler starts the task, reports deterministic progress steps, writes to a `.partial` sibling, finalizes the batch, atomically renames the file, and succeeds the task. On every exception it removes temporary/final artifacts created by this attempt and fails the task. Register it in `Services` so a submitted export can be consumed without adding a second task store.

- [ ] **Step 4: Verify GREEN**

Run Handler, task state-machine and XLSX tests together.

### Task 5: Export API, authorization, idempotency, and downloads

**Files:**
- Create: `app/api/schemas/exports_ds.py`
- Create: `app/api/routers/exports_ds.py`
- Modify: `app/api/main_ds.py`
- Modify: `app/api/routers/tasks_ds.py`
- Modify: `app/modules/identity_access/models_ds.py`
- Modify: `app/modules/identity_access/policy_ds.py`
- Test: `tests/api/test_exports_api_ds.py`

- [ ] **Step 1: Write failing API tests**

Cover preview, `202`, required idempotency key, replay, conflict, operator denial, finance success, task status/events, batch list/detail, missing batch, authorized download, missing file, and response bodies containing neither `file_path` nor internal URI.

```python
response = client.post(
    "/api/v1/exports",
    headers={"Idempotency-Key": "export-1", "X-Local-Roles": "FINANCE"},
    json={"filters": {}, "export_type": "PAYROLL"},
)
assert response.status_code == 202
assert set(response.json()) >= {"task_id", "status_url", "events_url"}
```

- [ ] **Step 2: Verify RED**

Run `uv run python -m pytest tests/api/test_exports_api_ds.py -q` and confirm the Router is absent.

- [ ] **Step 3: Implement the dedicated API**

Add `EXPORT_DOWNLOAD`, grant it only to ADMIN/FINANCE, and keep OPERATOR unchanged. Submit with operation `XLSX_EXPORT` and resource `EXPORTS`. Return safe batch DTOs. Authorize export-task status/events without granting FINANCE global task visibility. Stream downloads with a safe server-selected filename.

- [ ] **Step 4: Verify GREEN**

Run export API tests plus existing identity and tasks API tests.

### Task 6: API Client and React export center

**Files:**
- Create: `frontend/packages/api-client/src/exports_ds.ts`
- Modify: `frontend/packages/api-client/src/index_ds.ts`
- Create: `frontend/apps/web/src/ExportCenter_ds.tsx`
- Create: `frontend/apps/web/src/export-api.test.ts`
- Create: `frontend/apps/web/src/export-center.test.tsx`
- Modify: `frontend/apps/web/src/App.tsx`
- Modify: `frontend/apps/web/src/styles.css`

- [ ] **Step 1: Write failing API Client tests**

Mock `fetch` and assert preview query encoding, idempotency headers, task polling, batch listing and credential-safe download behavior.

- [ ] **Step 2: Verify RED**

Run `npm run test -w @form-detection/web -- export-api.test.ts` and confirm `ExportApi` is missing.

- [ ] **Step 3: Implement typed API Client**

Expose `ExportApi`, preview/batch/task DTOs and a download method that returns a `Blob` without accepting a local path.

- [ ] **Step 4: Write failing component tests**

Render `ExportCenter` with a fake API and assert preview exclusions, create button, progress state, history, download action and `REEXPORT_REQUIRED` re-export action.

- [ ] **Step 5: Verify RED, implement component, then verify GREEN**

Connect the existing “可导出” queue entry to `feature="exports"`, preserve unsaved-review navigation protection, and add focused responsive styles. Run all web tests, typecheck and build.

### Task 7: Documentation, full gates, and browser acceptance

**Files:**
- Modify: `PROGRESS.md`
- Modify: `docs/CURRENT_STATUS.md`
- Modify: `docs/NEXT_TASK.md`
- Modify: `docs/DECISIONS.md`
- Modify: `frontend/features/exports-trace/README.md`

- [ ] **Step 1: Run targeted gates**

```powershell
uv run python -m pytest tests/integration/test_xlsx_export.py tests/api/test_exports_api_ds.py tests/modules/test_reporting_handler_ds.py -q
uv run python -m ruff check app tests
uv run python -m mypy app config
Set-Location frontend
npm run test
npm run typecheck
npm run build:web
```

- [ ] **Step 2: Run full gates**

```powershell
uv run python -m pytest -q
uv run python -m ruff check .
uv run python -m mypy app config
Set-Location frontend
npm run test
npm run build:web
```

- [ ] **Step 3: Complete browser acceptance**

Start the local API/Web app with a FINANCE identity and execute preview → create → success → download → correct exported form → observe `REEXPORT_REQUIRED` → re-export → confirm old file exists and new batch supersedes it.

- [ ] **Step 4: Update project records**

Record exact test counts, commit IDs, completed scope, known limitations and the next task. Mark `NEXT_TASK.md` complete only after every automated and browser criterion has direct evidence.

- [ ] **Step 5: Final requirement audit**

Map every numbered scope item and acceptance bullet in `docs/NEXT_TASK.md` to a test, command output, API response, workbook inspection or browser observation. Do not declare completion when any evidence is missing.
