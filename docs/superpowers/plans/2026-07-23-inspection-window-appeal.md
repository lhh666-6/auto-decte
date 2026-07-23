# Inspection Window and Appeal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce one formal inspection per form with a two-hour queue window, manager early termination, a 24-hour appeal window, and durable user notifications.

**Architecture:** Supervisor approval creates one persisted inspection-window row and advances the form to plant audit. An atomic claim grants the first inspector exclusive submission rights. Plant audit is gated until a conforming result, natural expiry, or explicit manager termination. Appeals reuse the same window state, are restricted to one eligible inspector, and create a manager decision trail. Notifications are stored in a user message center; operating-system delivery is added in the PWA phase.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, Alembic, SQLite, React 18, TypeScript, Pytest, Vitest.

---

### Task 1: Persist inspection windows and notifications

**Files:**
- Create: `alembic/versions/019_bamboo_inspection_windows_ds.py`
- Modify: `app/adapters/database/models.py`
- Modify: `app/infrastructure/database/migrations.py`
- Test: `tests/integration/test_migrations_backup_integrity_ds.py`

- [ ] Add a failing migration test for inspection windows, one-result uniqueness, appeal fields, and durable notifications.
- [ ] Add revision 019 and ORM rows. Preserve old inspection data and do not fabricate windows for historical records.
- [ ] Verify migration and commit.

### Task 2: Open and gate the two-hour window

**Files:**
- Modify: `app/adapters/database/bamboo_process_repository_ds.py`
- Test: `tests/integration/test_bamboo_process_repository_ds.py`

- [ ] Add failing tests proving supervisor approval opens exactly one two-hour window and plant audit is blocked while it is active.
- [ ] Create the window in the supervisor transaction. Permit plant audit only after conforming completion, expiry, or manager termination; keep abnormal exceptions blocking.
- [ ] Verify and commit.

### Task 3: Implement queue, exclusive claim, and one formal result

**Files:**
- Modify: `app/application/bamboo_operations_ds.py`
- Modify: `app/api/schemas/bamboo_process_ds.py`
- Modify: `app/api/routers/mobile_bamboo_ds.py`
- Test: `tests/api/test_mobile_bamboo_operations_ds.py`

- [ ] Add failing API tests for all same-factory forms/cages, active/history buckets, first-claim exclusivity, one result per form, one-click conforming result, and abnormal text/photo/audio evidence validation.
- [ ] Add queue, claim, and submission operations with transactional ownership checks. Remove manual table-number search/selection from the inspection path.
- [ ] Retain completed and over-24-hour items as read-only history while removing them from active work.
- [ ] Verify and commit.

### Task 4: Add manager termination and 24-hour appeal

**Files:**
- Modify: `app/application/bamboo_operations_ds.py`
- Modify: `app/api/schemas/bamboo_process_ds.py`
- Modify: `app/api/routers/mobile_bamboo_ds.py`
- Test: `tests/api/test_mobile_bamboo_operations_ds.py`

- [ ] Add failing tests for manager-only early termination, inspector notification, original-claimant appeal priority, fallback first appeal claim, 24-hour expiry, and manager approval/rejection.
- [ ] Implement termination, appeal claim/submission, and decision operations. An approved abnormal appeal creates an open exception and returns the named production stage through the existing audit trail.
- [ ] Store all termination and appeal events in the message center.
- [ ] Verify and commit.

### Task 5: Build Android-first inspection and message UI

**Files:**
- Modify: `frontend/packages/api-client/src/mobile_ds.ts`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooRecordDetailPage.tsx`
- Modify: `frontend/apps/web/src/styles.css`
- Test: `frontend/apps/web/src/mobile/v3/BambooV3Pages.test.tsx`

- [ ] Add failing component tests for active/expired queue labels, countdown, claim ownership, explicit camera/record buttons, conforming shortcut, termination confirmation, appeal form, and read-only history.
- [ ] Implement responsive queue/detail controls. Use dedicated Android capture inputs for photos and audio; do not show a selectable table list inside the result form.
- [ ] Add a durable message-center panel and read state.
- [ ] Verify and commit.

### Task 6: Phase verification

- [ ] Run targeted backend tests, Ruff, mypy, targeted frontend tests, and frontend typecheck.
- [ ] Update `PROGRESS.md` with rules, endpoints, migration, and verification evidence.
- [ ] Commit the phase report.
