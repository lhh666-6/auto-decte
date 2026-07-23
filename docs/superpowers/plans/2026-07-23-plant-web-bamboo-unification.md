# Plant Web Bamboo Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the plant-manager Web workspace the only plant-manager client while preserving Bamboo as the single source for production, notifications, inspection, personnel and payroll, and make activated Managed Forms fully submittable from mobile.

**Architecture:** Keep Web cookie/CSRF authentication at the HTTP boundary, convert the Web actor to the existing `BambooActor`, and delegate all plant business operations to `BambooOperationsService` and `BambooProcessFacade`. Add a shared Managed Form resolver for list/schema/submit and add optimistic, idempotent semantics to the single Bamboo return command used by Web managers and mobile supervisors.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, Pydantic, React, TypeScript, Vitest, pytest.

---

### Task 1: Complete the Managed Form mobile submission path

**Files:**
- Modify: `app/modules/electronic_forms/governance_ds.py`
- Modify: `app/api/routers/mobile_definitions_ds.py`
- Modify: `app/api/routers/mobile_submissions_ds.py`
- Modify: `app/application/electronic_submissions_ds.py`
- Test: `tests/api/test_managed_forms_phase2_ds.py`

- [ ] **Step 1: Write a failing end-to-end submission test**

Extend the existing managed-form activation test with a real submission:

```python
submitted = mobile.post(
    "/api/v1/mobile/submissions",
    headers={"Idempotency-Key": "managed-daily-output-1"},
    json={
        "form_type": "DAILY_OUTPUT",
        "definition_version_id": version_id,
        "mode": "SELF",
        "subject_employee_code": "WORKER-A",
        "device_id": "android-a",
        "values": {"quantity": 12},
    },
)
assert submitted.status_code == 201
assert submitted.json()["status"] == "NEEDS_REVIEW"
```

Add separate failures for unknown fields, missing required fields, wrong type, inactive factory version and stale version.

- [ ] **Step 2: Run the focused test and verify RED**

Run:

```powershell
uv run --frozen --extra dev pytest tests/api/test_managed_forms_phase2_ds.py -q
```

Expected: the new submission assertion fails with `409 SCHEMA_VERSION_CONFLICT`.

- [ ] **Step 3: Add one authoritative resolver**

Add `ManagedFormService.resolve_active_form(plant_id, form_key, roles)` that returns the active version only when the owner role matches. Replace the duplicated list lookup in `mobile_definitions_ds.py` with this resolver.

- [ ] **Step 4: Validate and submit from the resolved version**

In `mobile_submissions_ds.py`, resolve either an active Managed Form or the legacy published definition. For Managed Forms:

```python
managed = ManagedFormService(services.engine).resolve_active_form(
    actor.factory_id,
    body.form_type,
    actor.roles,
)
definition_version_id = str(managed["version_id"])
schema = cast(dict[str, object], managed["schema_json"])
validate_managed_values(schema, body.values)
template_id = str(managed["form_key"])
template_version = str(managed["version"])
```

Construct the existing `ElectronicFormCommand` and preserve the receipt idempotency transaction.

- [ ] **Step 5: Run tests and verify GREEN**

Run:

```powershell
uv run --frozen --extra dev pytest tests/api/test_managed_forms_phase2_ds.py tests/api/test_mobile_submissions_ds.py tests/application/test_electronic_submissions_ds.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add app/modules/electronic_forms/governance_ds.py app/api/routers/mobile_definitions_ds.py app/api/routers/mobile_submissions_ds.py app/application/electronic_submissions_ds.py tests/api/test_managed_forms_phase2_ds.py
git commit -m "fix: complete managed mobile form submissions"
```

### Task 2: Make Bamboo return idempotent and revision-safe

**Files:**
- Create: `alembic/versions/028_bamboo_return_concurrency_ds.py`
- Modify: `app/adapters/database/models.py`
- Modify: `app/application/bamboo_operations_ds.py`
- Modify: `app/api/schemas/bamboo_process_ds.py`
- Modify: `app/api/routers/mobile_bamboo_ds.py`
- Modify: `app/infrastructure/database/migrations.py`
- Test: `tests/api/test_mobile_bamboo_operations_ds.py`
- Test: `tests/integration/test_retirement_migration_phase7_ds.py`

- [ ] **Step 1: Write failing idempotency and revision tests**

Add tests asserting:

```python
first = supervisor.post(
    f"/api/v1/mobile/bamboo/records/{record_id}/return",
    headers=_headers(supervisor, "return-1"),
    json={
        "target_stages": ["SORT"],
        "reason": "返工",
        "source": "SUPERVISOR",
        "expected_revision": 2,
    },
)
same = supervisor.post(
    f"/api/v1/mobile/bamboo/records/{record_id}/return",
    headers=_headers(supervisor, "return-1"),
    json=first_request,
)
assert same.json() == first.json()
assert stale.status_code == 409
assert stale.json()["detail"]["code"] == "REVISION_CONFLICT"
```

Also assert the same key with different payload returns `IDEMPOTENCY_CONFLICT`.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```powershell
uv run --frozen --extra dev pytest tests/api/test_mobile_bamboo_operations_ds.py -k "return and (idempotent or revision)" -q
```

Expected: schema rejects `expected_revision` or duplicate returns create different results.

- [ ] **Step 3: Add migration 028**

Add `actor_id`, `idempotency_key`, `payload_hash` and `result_payload` columns to `bamboo_returns`, backfill historical rows, and add:

```python
sa.UniqueConstraint(
    "actor_id",
    "idempotency_key",
    name="ux_bamboo_return_actor_idempotency",
)
```

Set `HEAD_REVISION = "028"`.

- [ ] **Step 4: Implement the single return command**

Change `selective_return()` to accept `expected_revision` and `idempotency_key`. Inside one transaction:

```python
existing = session.scalar(
    select(BambooReturnRow).where(
        BambooReturnRow.actor_id == actor.actor_id,
        BambooReturnRow.idempotency_key == idempotency_key,
    )
)
if existing:
    if existing.payload_hash != payload_hash:
        raise BambooOperationError("IDEMPOTENCY_CONFLICT", "幂等键已用于其他请求")
    return dict(existing.result_payload)
if record.revision != expected_revision:
    raise BambooOperationError(
        "REVISION_CONFLICT",
        "记录已更新，请刷新后重试",
        details={"expected_revision": expected_revision, "actual_revision": record.revision},
    )
```

Persist the resulting payload on the same `BambooReturnRow`.

- [ ] **Step 5: Pass the request values from mobile**

Add `expected_revision` to `SelectiveReturnRequest` and pass the validated `Idempotency-Key` into the service instead of discarding it.

- [ ] **Step 6: Verify migration and behavior**

Run:

```powershell
uv run --frozen --extra dev pytest tests/api/test_mobile_bamboo_operations_ds.py tests/integration/test_retirement_migration_phase7_ds.py -q
```

Expected: all tests pass and a fresh database reaches revision 028.

- [ ] **Step 7: Commit**

```powershell
git add alembic/versions/028_bamboo_return_concurrency_ds.py app/adapters/database/models.py app/application/bamboo_operations_ds.py app/api/schemas/bamboo_process_ds.py app/api/routers/mobile_bamboo_ds.py app/infrastructure/database/migrations.py tests/api/test_mobile_bamboo_operations_ds.py tests/integration/test_retirement_migration_phase7_ds.py
git commit -m "fix: protect bamboo returns from retries and races"
```

### Task 3: Rewire `/api/v1/plant/**` to Bamboo

**Files:**
- Modify: `app/application/bamboo_operations_ds.py`
- Rewrite: `app/api/routers/plant_workspace_ds.py`
- Create: `app/api/schemas/plant_workspace_ds.py`
- Test: `tests/api/test_web_workspaces_phase1_ds.py`
- Test: `tests/api/test_plant_bamboo_unification_ds.py`

- [ ] **Step 1: Write failing shared-source API tests**

Create Bamboo records, notifications, payroll facts, inspection windows and personnel transfers through existing services, then assert Web endpoints return those same IDs:

```python
production = manager.get("/api/v1/plant/production").json()
assert [item["record_id"] for item in production["records"]] == [record_id]

notifications = manager.get("/api/v1/plant/notifications").json()
assert notifications["items"][0]["notification_id"] == notification_id

payroll = manager.get("/api/v1/plant/payroll", params={"month": "2026-07"}).json()
assert payroll["items"][0]["employee_code"] == "SORT-1"
```

Assert no plant endpoint reads `finance_effective_records`, `submission_corrections`, `business_tasks`, `payroll_calculation_results` or `management_notifications`.

- [ ] **Step 2: Run the new API test and verify RED**

Run:

```powershell
uv run --frozen --extra dev pytest tests/api/test_plant_bamboo_unification_ds.py -q
```

Expected: Web production and payroll are empty while Bamboo rows exist.

- [ ] **Step 3: Add Web-to-Bamboo actor conversion**

In `plant_workspace_ds.py`:

```python
def _bamboo_actor(web_actor: WebActor) -> BambooActor:
    return BambooActor(
        actor_id=web_actor.employee_code,
        employee_code=web_actor.employee_code,
        employee_name=web_actor.employee_name,
        factory_id=web_actor.factory_id,
        factory_name=web_actor.factory_name,
        role=BambooRole.PLANT_MANAGER,
    )
```

- [ ] **Step 4: Add read-model methods to Bamboo operations**

Add focused methods for factory production records, workflow stage summaries and manager dashboard counts. Reuse existing repository, inspection queue, employee list, notification list, personnel transfer list and monthly summary methods.

- [ ] **Step 5: Replace plant route bindings**

Replace `SubmissionLedgerService`, `PayrollService` and `ManagedFormService.list_notifications()` use with Bamboo services. Add Web routes for:

- production detail and shared return;
- inspection queue and appeal decision;
- employees, role options and personnel transfers;
- notification read;
- Bamboo monthly payroll.

Keep `ManagedFormService` only for read-only activated forms and keep workflow approval absent.

- [ ] **Step 6: Verify shared-source APIs**

Run:

```powershell
uv run --frozen --extra dev pytest tests/api/test_plant_bamboo_unification_ds.py tests/api/test_web_workspaces_phase1_ds.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add app/application/bamboo_operations_ds.py app/api/routers/plant_workspace_ds.py app/api/schemas/plant_workspace_ds.py tests/api/test_plant_bamboo_unification_ds.py tests/api/test_web_workspaces_phase1_ds.py
git commit -m "fix: use bamboo as plant web source"
```

### Task 4: Move plant-manager workflows to Web UI

**Files:**
- Modify: `frontend/apps/web/src/app/router.tsx`
- Modify: `frontend/apps/web/src/web/WorkspaceShell.tsx`
- Modify: `frontend/apps/web/src/web/api.ts`
- Modify: `frontend/apps/web/src/web/types.ts`
- Modify: `frontend/apps/web/src/web/WorkspaceOverviewPage.tsx`
- Modify: `frontend/apps/web/src/web/PlantNotificationsPage.tsx`
- Modify: `frontend/apps/web/src/web/PlantProductionPage.tsx`
- Modify: `frontend/apps/web/src/web/PlantExceptionsPage.tsx`
- Modify: `frontend/apps/web/src/web/PlantWorkflowsPage.tsx`
- Modify: `frontend/apps/web/src/web/PayrollResultsPage.tsx`
- Create: `frontend/apps/web/src/web/PlantEmployeesPage.tsx`
- Test: `frontend/apps/web/src/web/plant-bamboo-unification.test.tsx`

- [ ] **Step 1: Write failing Web component tests**

Cover:

```tsx
expect(await screen.findByText("ZS-20260723-001")).toBeInTheDocument();
await user.click(screen.getByRole("button", { name: "选择环节打回" }));
await user.click(screen.getByLabelText("分选"));
await user.type(screen.getByLabelText("打回原因"), "需要重填");
await user.click(screen.getByRole("button", { name: "确认打回" }));
expect(fetch).toHaveBeenCalledWith(
  expect.stringContaining("/api/v1/plant/records/"),
  expect.objectContaining({
    method: "POST",
    headers: expect.objectContaining({ "Idempotency-Key": expect.any(String) }),
  }),
);
```

Also cover shared notification read, inspection appeal approval, personnel transfer display and Bamboo payroll rendering.

- [ ] **Step 2: Run Vitest and verify RED**

Run:

```powershell
npm test -w @form-detection/web -- --run src/web/plant-bamboo-unification.test.tsx
```

Expected: missing route/API/type assertions fail.

- [ ] **Step 3: Update API types and client**

Replace plant `FinanceRecord`, `SubmissionCorrection`, `BusinessTask` and governed `PayrollResult` calls with Bamboo record, notification, inspection, personnel and payroll types. Every Web write sends CSRF plus a stable per-attempt `Idempotency-Key`; return sends `expected_revision`.

- [ ] **Step 4: Update pages**

Make each plant page render the shared Bamboo response. Add `PlantEmployeesPage` and replace the current wildcard `/plant/employees` behavior. Remove every direct plant dependency on the parallel finance ledger.

- [ ] **Step 5: Verify frontend**

Run:

```powershell
npm test -w @form-detection/web -- --run src/web/plant-bamboo-unification.test.tsx src/web/web-workspaces.test.tsx
npm run typecheck -w @form-detection/web
```

Expected: tests and typecheck pass.

- [ ] **Step 6: Commit**

```powershell
git add frontend/apps/web/src/app/router.tsx frontend/apps/web/src/web
git commit -m "fix: move plant manager bamboo work to web"
```

### Task 5: Remove plant-manager access from mobile Bamboo APIs

**Files:**
- Modify: `app/api/routers/mobile_bamboo_ds.py`
- Test: `tests/api/test_mobile_bamboo_ds.py`
- Test: `tests/api/test_mobile_bamboo_operations_ds.py`
- Test: `tests/api/test_plant_bamboo_unification_ds.py`

- [ ] **Step 1: Write a failing access test**

```python
manager = _client(services, "MANAGER-1")
response = manager.get("/api/v1/mobile/bamboo/dashboard")
assert response.status_code == 403
assert response.json()["detail"]["code"] == "PLANT_MANAGER_WEB_ONLY"
```

Keep existing worker, supervisor and inspector expectations unchanged.

- [ ] **Step 2: Run and verify RED**

Run:

```powershell
uv run --frozen --extra dev pytest tests/api/test_mobile_bamboo_ds.py tests/api/test_mobile_bamboo_operations_ds.py -k "manager or supervisor or inspector" -q
```

Expected: manager still receives Bamboo mobile data.

- [ ] **Step 3: Enforce the boundary**

Reject `BambooRole.PLANT_MANAGER` in `_bamboo_actor()` with:

```python
raise HTTPException(
    status_code=403,
    detail={"code": "PLANT_MANAGER_WEB_ONLY", "detail": "厂长业务请使用 Web 工作区。"},
)
```

The Web adapter constructs its own `BambooActor`, so Web manager operations remain available.

- [ ] **Step 4: Run the mobile regression**

Run:

```powershell
uv run --frozen --extra dev pytest tests/api/test_mobile_bamboo_ds.py tests/api/test_mobile_bamboo_operations_ds.py tests/api/test_plant_bamboo_unification_ds.py -q
```

Expected: manager access test and all non-manager mobile tests pass.

- [ ] **Step 5: Commit**

```powershell
git add app/api/routers/mobile_bamboo_ds.py tests/api/test_mobile_bamboo_ds.py tests/api/test_mobile_bamboo_operations_ds.py tests/api/test_plant_bamboo_unification_ds.py
git commit -m "fix: keep plant managers on web"
```

### Task 6: Final consistency and boundary acceptance

**Files:**
- Modify: `docs/architecture/web-transformation-final-acceptance.md`
- Test: `tests/architecture/test_legacy_retirement_phase7_ds.py`
- Test: `tests/architecture/test_web_transformation_phase_0_ds.py`

- [ ] **Step 1: Add static boundary assertions**

Assert:

```python
source = Path("app/api/routers/plant_workspace_ds.py").read_text(encoding="utf-8")
for forbidden in (
    "SubmissionLedgerService",
    "PayrollService",
    "list_notifications(plant_id)",
):
    assert forbidden not in source
```

Assert the plant Web uses Bamboo APIs and `frontend/apps/web/src/mobile/**` remains unchanged.

- [ ] **Step 2: Run focused acceptance**

Run:

```powershell
uv run --frozen --extra dev pytest tests/api/test_managed_forms_phase2_ds.py tests/api/test_plant_bamboo_unification_ds.py tests/api/test_mobile_bamboo_ds.py tests/api/test_mobile_bamboo_operations_ds.py tests/architecture/test_web_transformation_phase_0_ds.py tests/architecture/test_legacy_retirement_phase7_ds.py -q
npm test -w @form-detection/web -- --run
```

Expected: all selected backend and all frontend tests pass.

- [ ] **Step 3: Run static checks**

Run:

```powershell
uv run --frozen --extra dev ruff check .
uv run --frozen --extra dev mypy
npm run typecheck -w @form-detection/web
git diff --check
uv run --frozen python scripts/check_mobile_boundary.py --base c05349fd6b3423f51e2774f68a3027612fcf806d --head HEAD
```

Expected: every command exits zero.

- [ ] **Step 4: Update acceptance documentation and commit**

Document the shared Bamboo sources, Web-only plant-manager boundary, revision 028 and exact test totals.

```powershell
git add docs/architecture/web-transformation-final-acceptance.md tests/architecture
git commit -m "docs: accept unified plant manager web"
```

- [ ] **Step 5: Synchronize current main branch**

Cherry-pick the isolated commits into `D:\半自动表单检测系统`, preserving unrelated user changes, migrate the local database to revision 028 after a recoverable backup, restart API/Web, and verify:

```text
GET /health/live  -> 200
GET /health/ready -> 200
GET /mobile/login -> rendered for worker/supervisor/inspector
GET /login        -> rendered for plant manager
```
