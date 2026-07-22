# Bamboo Process V3 Phase 1 Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a persistent, factory-scoped bamboo workflow vertical slice with strict stage visibility, immutable signed stage submissions, mobile task APIs, and a real mobile task/detail UI.

**Architecture:** Add a dedicated `app.modules.bamboo_process` domain with a SQLAlchemy repository and application service. Extend the mobile actor with one current factory/role assignment, enforce all stage transitions server-side, and replace the unavailable active-resource wizard with task/list/detail routes backed by the new API.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, pytest, React 18, TypeScript, React Router, Vitest.

**Completed:** 2026-07-22. Fresh verification: backend 468 tests passed; Ruff and Mypy passed; frontend 47 test files / 239 tests passed; API client and PWA production builds passed; a temporary SQLite database upgraded through Alembic revision `015` with all bamboo core tables present.

---

## File map

New backend files:

- `app/modules/bamboo_process/models_ds.py`: enums, immutable submissions, aggregate and domain errors.
- `app/modules/bamboo_process/state_machine_ds.py`: next-stage and role visibility rules.
- `app/modules/bamboo_process/ports_ds.py`: repository protocol.
- `app/modules/bamboo_process/facade_ds.py`: create/query/submit application-facing domain service.
- `app/adapters/database/bamboo_process_repository_ds.py`: SQLAlchemy mapping and optimistic persistence.
- `app/api/schemas/bamboo_process_ds.py`: Pydantic request/response contracts.
- `app/api/routers/mobile_bamboo_ds.py`: authenticated mobile endpoints.
- `alembic/versions/015_bamboo_process_core_ds.py`: factory, role assignment, record, stage submission and signature tables.
- `tests/modules/test_bamboo_process_state_machine_ds.py`: pure transition and visibility tests.
- `tests/integration/test_bamboo_process_repository_ds.py`: persistence and revision tests.
- `tests/api/test_mobile_bamboo_ds.py`: role/factory/API boundary tests.

Modified backend files:

- `app/application/mobile_identity_ds.py`: expose `factory_id`, `factory_name`, and `bamboo_role` in `MobileActor`/profiles.
- `app/adapters/database/mobile_identity_repository_ds.py`: persist and load the new assignment fields.
- `app/adapters/database/models.py`: add core rows.
- `app/infrastructure/database/migrations.py`: advance schema head to `015`.
- `app/services/container.py`: construct repository/facade and expose them in `Services`.
- `app/api/routers/mobile_ds.py`: include bamboo router.
- `app/api/schemas/mobile_ds.py`: return factory/role in login/session payloads.
- `app/api/routers/mobile_auth_ds.py`: map new actor fields.

New frontend files:

- `frontend/apps/web/src/mobile/bamboo/BambooTaskListPage.tsx`: available/waiting/completed task buckets.
- `frontend/apps/web/src/mobile/bamboo/BambooRecordDetailPage.tsx`: flow bar, current stage form and signed history.
- `frontend/apps/web/src/mobile/bamboo/BambooStageForm.tsx`: V3 moisture inputs and stage-specific fields.
- `frontend/apps/web/src/mobile/bamboo/bamboo.test.tsx`: navigation, visibility and submission UI tests.

Modified frontend files:

- `frontend/packages/api-client/src/mobile_ds.ts`: bamboo contracts/client methods and factory-aware session.
- `frontend/packages/api-client/src/mobile_ds.test.ts`: request contract coverage.
- `frontend/apps/web/src/mobile/MobileBambooProcessPage.tsx`: redirect/host the task-list entry instead of the unavailable cage wizard.
- `frontend/apps/web/src/app/router.tsx`: add task/detail routes.
- `frontend/apps/web/src/styles.css`: V3 green mobile cards, flow strip and stage form controls.

## Task 1: Domain aggregate and stage state machine

**Files:**
- Create: `app/modules/bamboo_process/__init__.py`
- Create: `app/modules/bamboo_process/models_ds.py`
- Create: `app/modules/bamboo_process/state_machine_ds.py`
- Test: `tests/modules/test_bamboo_process_state_machine_ds.py`

- [x] **Step 1: Write failing stage-order and visibility tests**

```python
from app.modules.bamboo_process.models_ds import BambooRole, BambooStage, StageSubmission
from app.modules.bamboo_process.state_machine_ds import next_stage, visible_to_role


def test_main_stage_order_requires_dipping_and_drying_signatures() -> None:
    assert next_stage([]) is BambooStage.SORT
    assert next_stage([StageSubmission.example(BambooStage.SORT)]) is BambooStage.DIPPING
    assert next_stage([
        StageSubmission.example(BambooStage.SORT),
        StageSubmission.example(BambooStage.DIPPING),
    ]) is BambooStage.DRYING
    assert next_stage([
        StageSubmission.example(BambooStage.SORT),
        StageSubmission.example(BambooStage.DIPPING),
        StageSubmission.example(BambooStage.DRYING),
    ]) is BambooStage.SUPERVISOR


def test_record_is_hidden_until_role_stage_is_open() -> None:
    submissions = [StageSubmission.example(BambooStage.SORT)]
    assert visible_to_role(submissions, BambooRole.DIPPING_OPERATOR)
    assert not visible_to_role(submissions, BambooRole.DRYING_RACK_OPERATOR)
    assert not visible_to_role(submissions, BambooRole.SUPERVISOR)
```

- [x] **Step 2: Run the test and verify missing module failure**

Run: `.venv\Scripts\python.exe -m pytest tests/modules/test_bamboo_process_state_machine_ds.py -q`  
Expected: FAIL with `ModuleNotFoundError: app.modules.bamboo_process`.

- [x] **Step 3: Implement stable enums, immutable submission and pure state machine**

```python
class BambooStage(StrEnum):
    SORT = "SORT"
    DIPPING = "DIPPING"
    DRYING = "DRYING"
    SUPERVISOR = "SUPERVISOR"
    PLANT_AUDIT = "PLANT_AUDIT"


class BambooRole(StrEnum):
    SORT_OPERATOR = "SORT_OPERATOR"
    DIPPING_OPERATOR = "DIPPING_OPERATOR"
    DRYING_RACK_OPERATOR = "DRYING_RACK_OPERATOR"
    INSPECTOR = "INSPECTOR"
    SUPERVISOR = "SUPERVISOR"
    PLANT_MANAGER = "PLANT_MANAGER"
    FINANCE_APPROVER = "FINANCE_APPROVER"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


STAGE_ROLE = {
    BambooStage.SORT: BambooRole.SORT_OPERATOR,
    BambooStage.DIPPING: BambooRole.DIPPING_OPERATOR,
    BambooStage.DRYING: BambooRole.DRYING_RACK_OPERATOR,
    BambooStage.SUPERVISOR: BambooRole.SUPERVISOR,
    BambooStage.PLANT_AUDIT: BambooRole.PLANT_MANAGER,
}
```

`next_stage()` must ignore invalidated submissions, return the first unsigned stage, and return `None` after plant audit. `visible_to_role()` must admit inspectors and supervisors only after drying, plant managers only after supervisor, finance only after plant audit, and system administrators for read-only audit.

- [x] **Step 4: Run domain tests**

Run: `.venv\Scripts\python.exe -m pytest tests/modules/test_bamboo_process_state_machine_ds.py -q`  
Expected: all tests PASS.

- [x] **Step 5: Commit domain state machine**

```powershell
git add app/modules/bamboo_process tests/modules/test_bamboo_process_state_machine_ds.py
git commit -m "feat(bamboo): add core stage state machine"
```

## Task 2: Persistent factory, role assignment and workflow schema

**Files:**
- Create: `alembic/versions/015_bamboo_process_core_ds.py`
- Modify: `app/adapters/database/models.py`
- Modify: `app/infrastructure/database/migrations.py`
- Modify: `tests/integration/test_migrations_backup_integrity_ds.py`

- [x] **Step 1: Add a failing migration test**

```python
def test_alembic_upgrade_creates_bamboo_process_core_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "bamboo-core.db"
    upgrade_database(database_path)
    engine = create_engine(f"sqlite:///{database_path}")
    tables = set(inspect(engine).get_table_names())
    assert {
        "bamboo_factories",
        "bamboo_role_definitions",
        "employee_bamboo_assignments",
        "bamboo_records",
        "bamboo_stage_submissions",
        "bamboo_signatures",
    } <= tables
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "015"
```

- [x] **Step 2: Run the migration test and verify failure**

Run: `.venv\Scripts\python.exe -m pytest tests/integration/test_migrations_backup_integrity_ds.py::test_alembic_upgrade_creates_bamboo_process_core_tables -q`  
Expected: FAIL because required tables do not exist and head is `014`.

- [x] **Step 3: Create migration 015 and matching ORM rows**

The migration must create the six tables from the test. `bamboo_records` includes `record_id`, `display_no`, `factory_id`, `source_type`, optional `source_ref`, `base_info` JSON, `current_stage`, `status`, `revision`, `created_by`, `created_at`, and `updated_at`. `bamboo_stage_submissions` has a unique `(record_id, stage_key, version)` constraint. `bamboo_signatures` stores actor/factory/role snapshots, `payload_hash`, service time, device ID, request ID and idempotency key.

Update:

```python
HEAD_REVISION = "015"
```

- [x] **Step 4: Run migration and metadata tests**

Run: `.venv\Scripts\python.exe -m pytest tests/integration/test_migrations_backup_integrity_ds.py -q`  
Expected: all migration tests PASS and existing upgrade scenarios now end at `015`.

- [x] **Step 5: Commit schema**

```powershell
git add alembic/versions/015_bamboo_process_core_ds.py app/adapters/database/models.py app/infrastructure/database/migrations.py tests/integration/test_migrations_backup_integrity_ds.py
git commit -m "feat(bamboo): persist factories roles and workflow records"
```

## Task 3: Factory-aware mobile identity

**Files:**
- Modify: `app/application/mobile_identity_ds.py`
- Modify: `app/adapters/database/mobile_identity_repository_ds.py`
- Modify: `app/api/schemas/mobile_ds.py`
- Modify: `app/api/routers/mobile_auth_ds.py`
- Modify: `tests/application/test_mobile_identity_ds.py`
- Modify: `tests/api/test_mobile_auth_ds.py`

- [x] **Step 1: Add failing actor/session tests**

```python
assert actor.factory_id == "FACTORY-A"
assert actor.factory_name == "竹丝一厂"
assert actor.bamboo_role == "SORT_OPERATOR"

session = client.get("/api/v1/mobile/auth/session")
assert session.json()["factory_id"] == "FACTORY-A"
assert session.json()["bamboo_role"] == "SORT_OPERATOR"
```

- [x] **Step 2: Run identity tests and verify missing fields**

Run: `.venv\Scripts\python.exe -m pytest tests/application/test_mobile_identity_ds.py tests/api/test_mobile_auth_ds.py -q`  
Expected: FAIL because actor/profile/session do not expose bamboo assignment fields.

- [x] **Step 3: Extend profile and actor with one current assignment**

Add fields with safe empty defaults to preserve existing callers:

```python
factory_id: str = ""
factory_name: str = ""
bamboo_role: str = ""
```

`set_access_profile()` receives the same keyword fields and persists them in the assignment table, while existing generic `roles` and allowed-form lists remain compatible. Login/session responses expose the three fields.

- [x] **Step 4: Run identity tests**

Run: `.venv\Scripts\python.exe -m pytest tests/application/test_mobile_identity_ds.py tests/api/test_mobile_auth_ds.py -q`  
Expected: PASS.

- [x] **Step 5: Commit factory-aware identity**

```powershell
git add app/application/mobile_identity_ds.py app/adapters/database/mobile_identity_repository_ds.py app/api/schemas/mobile_ds.py app/api/routers/mobile_auth_ds.py tests/application/test_mobile_identity_ds.py tests/api/test_mobile_auth_ds.py
git commit -m "feat(mobile): expose factory bamboo assignment"
```

## Task 4: Repository and optimistic workflow service

**Files:**
- Create: `app/modules/bamboo_process/ports_ds.py`
- Create: `app/modules/bamboo_process/facade_ds.py`
- Create: `app/adapters/database/bamboo_process_repository_ds.py`
- Test: `tests/integration/test_bamboo_process_repository_ds.py`
- Test: `tests/modules/test_bamboo_process_facade_ds.py`

- [x] **Step 1: Write failing persistence and service tests**

```python
record = service.create_record(
    actor=sort_actor,
    base_info={"cage_no": "3-018", "length": "2.3", "grade": "A", "bundle_count": 16},
    source_type="MOBILE_CREATED",
    source_ref=None,
)
signed = service.submit_stage(
    record.record_id,
    actor=sort_actor,
    stage=BambooStage.SORT,
    values={"moisture": [12, 13, 12]},
    expected_revision=1,
    idempotency_key="sort-1",
    device_id="device-a",
    request_id="request-a",
)
assert signed.current_stage is BambooStage.DIPPING
assert repository.get(record.record_id).revision == 2
```

Also assert duplicate idempotency keys return the original result, stale revisions raise `StaleBambooRevision`, wrong roles raise `BambooPermissionDenied`, and cross-factory access returns no visible record.

- [x] **Step 2: Run tests and verify missing service/repository**

Run: `.venv\Scripts\python.exe -m pytest tests/modules/test_bamboo_process_facade_ds.py tests/integration/test_bamboo_process_repository_ds.py -q`  
Expected: FAIL with missing imports.

- [x] **Step 3: Implement repository protocol, SQL adapter and facade**

The facade methods are:

```python
def create_record(self, *, actor: BambooActor, base_info: dict[str, object], source_type: str, source_ref: str | None) -> BambooRecord: ...
def list_tasks(self, *, actor: BambooActor, bucket: TaskBucket) -> list[BambooRecord]: ...
def get_visible(self, record_id: str, *, actor: BambooActor) -> BambooRecord | None: ...
def submit_stage(self, record_id: str, *, actor: BambooActor, stage: BambooStage, values: dict[str, object], expected_revision: int, idempotency_key: str, device_id: str, request_id: str) -> BambooRecord: ...
```

The repository saves the stage submission, signature and aggregate revision in one SQLAlchemy transaction. The payload hash uses canonical `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)` and SHA-256.

- [x] **Step 4: Run service and repository tests**

Run: `.venv\Scripts\python.exe -m pytest tests/modules/test_bamboo_process_facade_ds.py tests/integration/test_bamboo_process_repository_ds.py -q`  
Expected: PASS.

- [x] **Step 5: Commit core persistence behavior**

```powershell
git add app/modules/bamboo_process app/adapters/database/bamboo_process_repository_ds.py tests/modules/test_bamboo_process_facade_ds.py tests/integration/test_bamboo_process_repository_ds.py
git commit -m "feat(bamboo): add persistent signed workflow service"
```

## Task 5: Authenticated mobile bamboo API

**Files:**
- Create: `app/api/schemas/bamboo_process_ds.py`
- Create: `app/api/routers/mobile_bamboo_ds.py`
- Modify: `app/api/routers/mobile_ds.py`
- Modify: `app/services/container.py`
- Test: `tests/api/test_mobile_bamboo_ds.py`

- [x] **Step 1: Write failing API tests**

Cover:

```python
created = sort_client.post(
    "/api/v1/mobile/bamboo/records",
    headers=write_headers(sort_client, "create-1"),
    json={"base_info": {"cage_no": "3-018", "length": "2.3", "grade": "A", "bundle_count": 16}},
)
assert created.status_code == 201

hidden = drying_client.get(f"/api/v1/mobile/bamboo/records/{record_id}")
assert hidden.status_code in {403, 404}

signed = sort_client.post(
    f"/api/v1/mobile/bamboo/records/{record_id}/stages/SORT/submit",
    headers=write_headers(sort_client, "sort-1"),
    json={"expected_revision": 1, "device_id": "sort-phone", "values": {"moisture": [12, 13]}},
)
assert signed.status_code == 200
assert dipping_client.get(f"/api/v1/mobile/bamboo/records/{record_id}").status_code == 200
```

Also cover CSRF, missing idempotency key, cross-factory access, wrong role, stale revision and dashboard bucket counts.

- [x] **Step 2: Run API tests and verify 404 route failure**

Run: `.venv\Scripts\python.exe -m pytest tests/api/test_mobile_bamboo_ds.py -q`  
Expected: FAIL because `/api/v1/mobile/bamboo` routes do not exist.

- [x] **Step 3: Implement schemas, router and service wiring**

Routes:

```text
GET  /api/v1/mobile/bamboo/dashboard
GET  /api/v1/mobile/bamboo/tasks?bucket=available|waiting|completed
POST /api/v1/mobile/bamboo/records
GET  /api/v1/mobile/bamboo/records/{record_id}
POST /api/v1/mobile/bamboo/records/{record_id}/stages/{stage_key}/submit
```

Map domain errors to stable problem codes: `RECORD_NOT_VISIBLE`, `STAGE_NOT_AVAILABLE`, `BAMBOO_ROLE_REQUIRED`, and `STALE_REVISION`.

- [x] **Step 4: Run API tests and mobile regression tests**

Run: `.venv\Scripts\python.exe -m pytest tests/api/test_mobile_bamboo_ds.py tests/api/test_mobile_auth_ds.py tests/api/test_mobile_submissions_ds.py -q`  
Expected: PASS.

- [x] **Step 5: Commit mobile API**

```powershell
git add app/api/schemas/bamboo_process_ds.py app/api/routers/mobile_bamboo_ds.py app/api/routers/mobile_ds.py app/services/container.py tests/api/test_mobile_bamboo_ds.py
git commit -m "feat(api): expose bamboo mobile workflow"
```

## Task 6: Frontend bamboo client contracts

**Files:**
- Modify: `frontend/packages/api-client/src/mobile_ds.ts`
- Modify: `frontend/packages/api-client/src/mobile_ds.test.ts`

- [x] **Step 1: Add failing client request tests**

```typescript
await client.listBambooTasks("available");
expect(fetcher).toHaveBeenCalledWith(
  "/api/v1/mobile/bamboo/tasks?bucket=available",
  expect.objectContaining({ credentials: "same-origin" }),
);

await client.submitBambooStage("BR-1", "SORT", {
  expected_revision: 1,
  device_id: "phone-a",
    values: { moisture: [12, 13] },
}, "sort-1");
expect(fetcher).toHaveBeenLastCalledWith(
  "/api/v1/mobile/bamboo/records/BR-1/stages/SORT/submit",
  expect.objectContaining({ method: "POST" }),
);
```

- [x] **Step 2: Run client tests and verify missing methods**

Run: `npm.cmd test -w packages/api-client` from `frontend`  
Expected: FAIL with TypeScript errors for missing bamboo methods.

- [x] **Step 3: Add typed session, task, record and submission contracts**

Add `factory_id`, `factory_name`, `bamboo_role` to `MobileSession` and implement `getBambooDashboard`, `listBambooTasks`, `createBambooRecord`, `getBambooRecord`, and `submitBambooStage`. All writes use existing CSRF handling and pass `Idempotency-Key`.

- [x] **Step 4: Run client tests**

Run: `npm.cmd test -w packages/api-client` from `frontend`  
Expected: PASS.

- [x] **Step 5: Commit client contract**

```powershell
git add frontend/packages/api-client/src/mobile_ds.ts frontend/packages/api-client/src/mobile_ds.test.ts
git commit -m "feat(api-client): add bamboo workflow contracts"
```

## Task 7: Real mobile task and detail UI

**Files:**
- Create: `frontend/apps/web/src/mobile/bamboo/BambooTaskListPage.tsx`
- Create: `frontend/apps/web/src/mobile/bamboo/BambooRecordDetailPage.tsx`
- Create: `frontend/apps/web/src/mobile/bamboo/BambooStageForm.tsx`
- Create: `frontend/apps/web/src/mobile/bamboo/bamboo.test.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileBambooProcessPage.tsx`
- Modify: `frontend/apps/web/src/app/router.tsx`
- Modify: `frontend/apps/web/src/styles.css`

- [x] **Step 1: Write failing UI tests**

Render the pages with mocked client responses and assert:

```typescript
expect(screen.getByRole("heading", { name: "记录工作" })).toBeInTheDocument();
expect(screen.getByText("ZS-20260722-018")).toBeInTheDocument();
expect(screen.queryByText("未开放记录")).not.toBeInTheDocument();

await user.click(screen.getByRole("button", { name: "增加检测点" }));
expect(screen.getAllByLabelText(/含水率检测点/)).toHaveLength(9);
await user.click(screen.getByRole("button", { name: "删除最后一个" }));
expect(screen.getAllByLabelText(/含水率检测点/)).toHaveLength(8);

```

- [x] **Step 2: Run UI tests and verify missing components**

Run: `npm.cmd test -w apps/web -- bamboo.test.tsx` from `frontend`  
Expected: FAIL because bamboo pages do not exist.

- [x] **Step 3: Implement V3 task list, detail skeleton and stage forms**

Use the approved green V3 mobile style, four-tab shell, horizontal flow strip, 44px controls, 16px inputs and a confirmation summary. `MobileBambooProcessPage` becomes the `/mobile/record/bamboo-process` entry and renders/redirects to task list; detail actions appear only for the stage returned by the server.

- [x] **Step 4: Run UI and full frontend tests**

Run: `npm.cmd test -w apps/web -- bamboo.test.tsx` from `frontend`  
Expected: PASS.  
Run: `npm.cmd test` from `frontend`  
Expected: all frontend tests PASS.

- [x] **Step 5: Commit mobile UI**

```powershell
git add frontend/apps/web/src/mobile/bamboo frontend/apps/web/src/mobile/MobileBambooProcessPage.tsx frontend/apps/web/src/app/router.tsx frontend/apps/web/src/styles.css
git commit -m "feat(mobile): replace bamboo wizard with workflow tasks"
```

## Task 8: Phase 1 verification and documentation

**Files:**
- Modify: `docs/acceptance-report.md` only if it has no unrelated user changes in this worktree.
- Modify: `docs/superpowers/plans/2026-07-22-bamboo-process-v3-phase-1-core.md`

- [x] **Step 1: Run backend focused suite**

Run:

```powershell
.venv\Scripts\python.exe -m pytest tests/modules/test_bamboo_process_state_machine_ds.py tests/modules/test_bamboo_process_facade_ds.py tests/integration/test_bamboo_process_repository_ds.py tests/api/test_mobile_bamboo_ds.py -q
```

Expected: PASS.

- [x] **Step 2: Run backend full suite and static checks**

Run:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check app tests
.venv\Scripts\python.exe -m mypy app config
```

Expected: all commands exit 0.

- [x] **Step 3: Run frontend full suite and build**

Run:

```powershell
npm.cmd test
npm.cmd run build -w packages/api-client
npm.cmd run build -w apps/web
```

Expected: all commands exit 0.

- [x] **Step 4: Run database upgrade smoke test**

Create a temporary SQLite database, run `upgrade_database`, and assert Alembic revision `015`; never migrate `data/database/demo.db` during automated verification.

- [x] **Step 5: Mark completed plan checkboxes and commit verification notes**

```powershell
git add docs/superpowers/plans/2026-07-22-bamboo-process-v3-phase-1-core.md
git commit -m "docs: record bamboo phase 1 verification"
```

## Later implementation plans

After this vertical slice passes, create and execute separate plans for:

1. Phase 2: versioned payroll rules,分选工资、浸胶/干燥联合工资和调整事实。
2. Phase 3: multi-inspection, evidence upload, exception closure and supervisor evaluation.
3. Phase 4: selective returns, 12-hour plant audit, correction chains and role-change approval.
4. Phase 5: daily XLSX item approval, finance inquiry, partial release, supplement batches and monthly summaries.

Each phase must start from passing Phase 1 tests and produce a deployable, backward-compatible increment.
