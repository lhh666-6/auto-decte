# Android Install and System Notifications Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Android installation a one-click system prompt and optionally mirror durable bamboo messages to operating-system notifications without affecting business transactions.

**Architecture:** Keep `beforeinstallprompt` as the only install mechanism and surface a short Chrome menu fallback when it is unavailable. Add a focused notification preference/delivery module that polls the existing durable message API while an authenticated PWA is running, records locally delivered notification IDs per employee, and prefers service-worker notifications with a browser notification fallback. Delivery never marks a message read and all failures are isolated from the mobile shell.

**Tech Stack:** React 18, TypeScript, Vite PWA/Workbox, Web Notifications API, Service Worker API, Vitest/jsdom.

---

### Task 1: Verify one-click Android installation

**Files:**
- Modify: `frontend/apps/web/src/mobile/pwa/usePwaInstall.ts`
- Create: `frontend/apps/web/src/mobile/pwa/usePwaInstall.test.tsx`
- Modify: `frontend/apps/web/src/mobile/v3/BambooV3ProfilePage.tsx`

- [ ] Add a hook test that dispatches `beforeinstallprompt`, clicks install once, and proves `prompt()` is called exactly once and the accepted result becomes installed.
- [ ] Run `npm.cmd run test -w @form-detection/web -- usePwaInstall.test.tsx` and confirm it fails before any production change.
- [ ] Keep the deferred prompt until accepted, handle `appinstalled`, and return only `installed`, `dismissed`, or `unavailable`.
- [ ] Change the unavailable profile message to the concise fallback: “Chrome 右上角菜单 → 安装应用/添加到主屏幕”. Do not claim that a web page can bypass Android confirmation.
- [ ] Re-run the hook/profile tests and commit.

### Task 2: Add opt-in system notification delivery

**Files:**
- Create: `frontend/apps/web/src/mobile/notifications/system-notifications.ts`
- Create: `frontend/apps/web/src/mobile/notifications/useBambooSystemNotifications.ts`
- Create: `frontend/apps/web/src/mobile/notifications/system-notifications.test.ts`
- Modify: `frontend/apps/web/src/mobile/v3/MobileV3Shell.tsx`
- Modify: `frontend/apps/web/src/mobile/v3/BambooV3ProfilePage.tsx`

- [ ] Add failing tests proving permission is requested only from a user action, denied/unsupported environments remain disabled, an unread durable message is shown once, and the same notification ID is not shown twice.
- [ ] Run `npm.cmd run test -w @form-detection/web -- system-notifications.test.ts` and confirm the expected failures.
- [ ] Implement preference key `bamboo-system-notifications:<employee_code>` and delivered-ID key `bamboo-system-notification-delivered:<employee_code>`.
- [ ] Implement `showBambooSystemNotification`: prefer `ServiceWorkerRegistration.showNotification`; otherwise use `new Notification`; catch and return failure without throwing into business UI.
- [ ] Implement the authenticated shell hook: poll `listBambooNotifications()` every 30 seconds and on visibility/focus, deliver only unread and locally undelivered IDs, cap one poll to the three newest messages, and retain message-center records/read state unchanged.
- [ ] Add “开启消息弹窗/消息弹窗已开启/浏览器已拒绝通知” state to the profile page. The enable button directly calls `Notification.requestPermission()` from the click handler.
- [ ] Run targeted tests and commit.

### Task 3: Final verification and progress record

**Files:**
- Modify: `PROGRESS.md`

- [ ] Run `npm.cmd run test -w @form-detection/api-client`, `npm.cmd run test -w @form-detection/web`, `npm.cmd run typecheck`, `npm.cmd run build:web`, the bamboo backend test, Ruff, and mypy.
- [ ] Confirm Android constraints in the progress record: one click opens the native prompt; Android confirmation remains mandatory; system notification mirroring works only after permission and while the PWA/browser runtime can execute.
- [ ] Record exact passing counts and commits in `PROGRESS.md`.
- [ ] Commit the phase report.

## Self-review

- Spec coverage: install event, installed state, concise fallback, explicit authorization, durable message preservation, OS notification isolation, Android/PWA runtime limitation, and verification are all assigned.
- Placeholder scan: no deferred implementation or unspecified error handling remains.
- Type consistency: notification preference and delivered keys are employee-scoped; `BambooNotification.notification_id`, `title`, `body`, and `read_at` come from the existing API client type.
