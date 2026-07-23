# Personnel Transfer and Payroll Access Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace worker self-service role changes with manager-initiated, admin-executed transfers and enforce least-privilege payroll visibility.

**Architecture:** A new transfer request is initiated by the source plant manager. Internal transfers become admin-pending immediately; cross-factory transfers require approvals from both source and target managers before an admin may execute them. Manager replacement is an admin-only direct operation. Execution updates assignment and mobile profile in one transaction and writes a durable employee notification. Payroll projections are filtered centrally by actor scope.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, SQLite, React 18, TypeScript, Pytest, Vitest.

---

### Task 1: Persist governed personnel transfers

**Files:**
- Create: `alembic/versions/020_bamboo_personnel_transfers_ds.py`
- Modify: `app/adapters/database/models.py`
- Modify: `app/infrastructure/database/migrations.py`
- Test: `tests/integration/test_migrations_backup_integrity_ds.py`

- [ ] Add a failing migration test for transfer type, source/target factories, both manager decisions, admin execution, revision, and audit timestamps.
- [ ] Add revision 020 and ORM model without rewriting historical role-change rows.
- [ ] Verify and commit.

### Task 2: Enforce manager initiation and admin execution

**Files:**
- Modify: `app/application/bamboo_operations_ds.py`
- Modify: `app/api/schemas/bamboo_process_ds.py`
- Modify: `app/api/routers/mobile_bamboo_ds.py`
- Test: `tests/api/test_mobile_bamboo_operations_ds.py`

- [ ] Add failing tests proving workers have no self-request endpoint, internal changes require admin execution, cross-factory changes require both managers, admins cannot bypass either approval, and only admins replace plant managers.
- [ ] Add list/create/manager-decision/admin-execute operations with factory and role validation.
- [ ] Execute assignment/profile changes atomically and notify the transferred employee.
- [ ] Remove manager direct assignment of existing employees; retain initial assignment for newly created staff.
- [ ] Verify and commit.

### Task 3: Enforce payroll visibility

**Files:**
- Modify: `app/application/bamboo_operations_ds.py`
- Modify: `app/api/routers/mobile_bamboo_ds.py`
- Test: `tests/api/test_mobile_bamboo_operations_ds.py`

- [ ] Add failing tests for employee-self only, own-factory manager, global finance, and global admin payroll access.
- [ ] Filter record payroll projections and monthly summaries centrally. Finance/admin queries span factories; managers remain factory-scoped.
- [ ] Verify and commit.

### Task 4: Build independent personnel workspace

**Files:**
- Modify: `frontend/packages/api-client/src/mobile_ds.ts`
- Modify: `frontend/apps/web/src/mobile/v3/BambooV3ProfilePage.tsx`
- Create: `frontend/apps/web/src/mobile/personnel/BambooPersonnelPage.tsx`
- Modify: mobile routing/navigation and styles
- Test: `frontend/apps/web/src/mobile/v3/BambooV3Pages.test.tsx`

- [ ] Add failing tests proving workers see no self-request control and managers/admins use an independent responsive personnel page.
- [ ] Implement employee selection, internal/cross-factory request creation, approval state, and admin execution views for mobile and wide screens.
- [ ] Show transfer completion in the employee message center.
- [ ] Verify and commit.

### Task 5: Phase verification

- [ ] Run targeted backend tests, Ruff, mypy, API-client tests, frontend tests, and TypeScript checks.
- [ ] Update `PROGRESS.md` with rules, migration, endpoints, and verification evidence.
- [ ] Commit the phase report.
