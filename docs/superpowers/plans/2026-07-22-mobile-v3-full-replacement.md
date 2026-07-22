# Mobile V3 Full Replacement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace every routed legacy mobile screen with the Bamboo V3 interface while retaining the formal API, session, offline-draft, and PWA capabilities.

**Architecture:** Keep the existing React router and mobile session boundary, but route all authenticated mobile navigation through one V3 shell. Compose focused V3 home, work, submissions, profile, record-detail, navigation, and icon components around `MobileApiClient`; redirect every legacy mobile URL into this information architecture. Repair demo identities through an idempotent backend utility and prevent development Service Workers from serving the removed shell.

**Tech Stack:** React 18, React Router 6, TypeScript, Vite PWA/Workbox, FastAPI, SQLAlchemy, Vitest/Testing Library, Pytest.

---

### Task 1: Lock the V3 routing and shell contract

**Files:**
- Create: `frontend/apps/web/src/mobile/v3/MobileV3Shell.test.tsx`
- Create: `frontend/apps/web/src/mobile/v3/MobileV3Shell.tsx`
- Create: `frontend/apps/web/src/mobile/v3/MobileV3Icon.tsx`
- Modify: `frontend/apps/web/src/app/router.tsx`
- Modify: `frontend/apps/web/src/styles.css`

- [ ] **Step 1: Write failing tests** asserting exactly four navigation labels, SVG icons, a V3 shell marker, and redirects from `/mobile/record`, `/mobile/drafts`, `/mobile/outbox`, and `/mobile/record/bamboo-process/:id`.
- [ ] **Step 2: Run** `npm test -w @form-detection/web -- --run src/mobile/v3/MobileV3Shell.test.tsx`; expect missing V3 shell and five legacy navigation items.
- [ ] **Step 3: Implement** `MobileV3Shell` with four `NavLink`s (`/mobile/home`, `/mobile/work`, `/mobile/submissions`, `/mobile/profile`), inline SVG icons, `520px` centered layout, `100dvh`, safe-area padding, and compatibility `Navigate replace` routes.
- [ ] **Step 4: Re-run the focused test** and expect PASS.
- [ ] **Step 5: Commit** with `feat(mobile): replace legacy shell with V3 navigation`.

### Task 2: Replace login and home with the V3 experience

**Files:**
- Create: `frontend/apps/web/src/mobile/v3/BambooV3HomePage.test.tsx`
- Create: `frontend/apps/web/src/mobile/v3/BambooV3HomePage.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileLoginPage.tsx`
- Modify: `frontend/apps/web/src/styles.css`
- Modify: `frontend/apps/web/public/manifest.webmanifest`

- [ ] **Step 1: Write failing tests** for the green V3 hero, current factory/role, online indicator, three dashboard totals, role-aware work action, and absence of “可填写的记录类型”.
- [ ] **Step 2: Run the test** and verify the old generic home fails the assertions.
- [ ] **Step 3: Implement** the V3 home using `getBambooDashboard()` and session metadata; show the pending-role state when `bamboo_role` is empty. Finance accounts must see a handoff message and link to the web approval interface, never mobile approval actions. Restyle login and manifest colors to `#17653a`/`#f3f5f4`.
- [ ] **Step 4: Re-run the focused test** and expect PASS.
- [ ] **Step 5: Commit** with `feat(mobile): add V3 login and role home`.

### Task 3: Make V3 work, detail, submissions, and profile the only pages

**Files:**
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooTaskListPage.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooRecordDetailPage.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooStageForm.tsx`
- Modify: `frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx`
- Create: `frontend/apps/web/src/mobile/v3/BambooV3SubmissionsPage.tsx`
- Create: `frontend/apps/web/src/mobile/v3/BambooV3ProfilePage.tsx`
- Create: `frontend/apps/web/src/mobile/v3/BambooV3Pages.test.tsx`
- Modify: `frontend/apps/web/src/styles.css`

- [ ] **Step 1: Write failing tests** for V3 work tabs/cards, record flow, current-user submission grouping, profile identity, worker role-change entry, finance exclusion from mobile approval, and no links to legacy standalone drafts/outbox.
- [ ] **Step 2: Run the test** and verify missing V3 pages fail.
- [ ] **Step 3: Implement** focused V3 pages. Work uses Bamboo task buckets; submissions combines waiting/completed records with IndexedDB draft/outbox counts; profile exposes identity/network/version/logout and role controls. Convert detail actions to V3 cards and bottom-sheet presentation without changing API contracts.
- [ ] **Step 4: Re-run V3 page and existing Bamboo tests** and expect PASS.
- [ ] **Step 5: Commit** with `feat(mobile): complete V3 work and account pages`.

### Task 4: Repair Chinese demo identities idempotently

**Files:**
- Create: `app/tools/repair_bamboo_demo_ds.py`
- Create: `tests/tools/test_repair_bamboo_demo_ds.py`

- [ ] **Step 1: Write a failing Pytest** that stores `???` for the seven demo employees/factory, runs `repair_bamboo_demo_data(engine)`, and expects the specified Chinese names, positions, team, factory, and unchanged assignments.
- [ ] **Step 2: Run** `pytest tests/tools/test_repair_bamboo_demo_ds.py -q`; expect import/function failure.
- [ ] **Step 3: Implement** an idempotent SQLAlchemy repair function and CLI entry that only updates known demo identifiers and never creates production credentials.
- [ ] **Step 4: Re-run the focused test** and execute the repair against `data/database/demo.db`.
- [ ] **Step 5: Verify** a proxied login for `ZS001` returns `王分选`, `竹丝示范一厂`, and `分选工`.
- [ ] **Step 6: Commit** with `fix(demo): repair Bamboo Chinese identities`.

### Task 5: Remove stale PWA shell behavior

**Files:**
- Modify: `frontend/apps/web/src/pwa/register-sw.ts`
- Modify: `frontend/apps/web/src/pwa/pwa-cache-policy.test.ts`
- Modify: `frontend/apps/web/vite.config.ts`

- [ ] **Step 1: Write a failing test** that development registration unregisters existing Service Workers and clears only application-owned caches, while production still prompts for updates.
- [ ] **Step 2: Run the PWA test** and verify current unconditional registration fails.
- [ ] **Step 3: Implement** development cleanup and bump the Workbox cache prefix/version for the V3 release.
- [ ] **Step 4: Re-run PWA tests and build** with `npm run build:web`; expect PASS and a generated service worker containing the V3 cache identifier.
- [ ] **Step 5: Commit** with `fix(pwa): retire cached legacy mobile shell`.

### Task 6: Full verification and integration

**Files:**
- Modify only files required by discovered regressions.

- [ ] **Step 1: Run backend quality checks:** `ruff check app alembic tests config`, `mypy app config`, and `pytest -q`.
- [ ] **Step 2: Run frontend checks:** `npm test`, `npm test -w @form-detection/api-client`, and `npm run build:web`.
- [ ] **Step 3: Restart API/Vite**, verify `/mobile/login`, login redirect, four navigation items, correct Chinese identity, and `/mobile/work` over the proxy.
- [ ] **Step 4: Fast-forward merge** `codex/mobile-v3-replacement` into `modular-architecture` while preserving the root worktree's unrelated dirty files.
