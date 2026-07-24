# P1/P2 Outbox 用户隔离收口报告

> 日期: 2026-07-24
> 分支: modular-architecture（未提交）
> 状态: P1.9 COMPLETE

---

## 1. 结论

**PASS** — `runFlush` 已实现严格的用户作用域隔离，所有 6 项安全检查全部通过。

---

## 2. 根因

修改前 `runFlush()` 调用 `listPending()` 无 owner 参数，读取 IndexedDB 中全部用户的所有 PENDING 条目并逐条通过 `mobileApiClient.createSubmission()` 发送。`mobileApiClient` 使用浏览器自动附加的当前登录 session cookie。

**风险链路**:
```
A 离线 → A's Outbox 写入 IndexedDB
A 退出 → B 登录 → 网络恢复
flushPendingOutbox() → runFlush() → listPending() [ALL users]
→ createSubmission(A's data) [UNDER B's COOKIE]
→ A 的数据被 B 的身份提交到后台
```

---

## 3. 最终同步模型

```
authenticated owner (来自 MobileSession.sessionMetadata.employee_code)
    ↓
flushPendingOutbox(owner)
    ↓ owner === "" ? → no-op (fail-closed)
    ↓
runFlush(owner)
    ↓
listPending(owner)  ← 只查询 owner 的 PENDING 条目
    ↓
for each entry:
    defense-in-depth: entry.owner !== owner → skip + console.warn
    ↓
    markSubmitting → createSubmission → remove
```

**无 owner 时行为**: `flushPendingOutbox()` / `flushPendingOutbox("")` 返回 `{ succeeded: 0, ... }`，不调用任何网络请求。

---

## 4. Legacy 数据策略

| 场景 | 行为 |
|------|------|
| `owner: ""` (空字符串) | `listPending("EMP-A")` 不返回（`owner` filter 要求精确匹配） |
| `owner: ""` 被 flush | `runFlush` defense-in-depth guard 跳过（`"" !== "EMP-A"`） |
| `owner: undefined` | 同空字符串 — IndexedDB schema 已含 `owner: string` 字段 |
| 自动归属当前用户 | **绝不** — 没有任何代码路径将 ownerless entry 的 owner 改为当前用户 |
| 自动提交 | **绝不** — 任何 filter/guard 都不会让 ownerless 条目通过 |

---

## 5. 修改文件

| 文件 | 改动 | 原因 |
|------|------|------|
| `sync/SubmissionCoordinator.ts` | `flushPendingOutbox(owner?)` + `runFlush(owner)` + defense-in-depth guard | 核心安全修复 |
| `session/MobileSessionProvider.tsx` | 两处 `flushPendingOutbox()` → 传入 `sessionMetadata?.employee_code` | 调用点适配 |
| `mobile/MobileOutboxPage.tsx` | 重试按钮传入 `sessionMetadata?.employee_code` | 调用点适配 |
| `sync/submission-coordinator.test.ts` | 更新 5 个现有测试 + 新增 8 个 owner isolation 测试 | 安全验证 |
| `storage/outbox-owner-isolation.test.ts` | 新建 7 个 outbox 级别 owner 隔离测试 | 安全验证 |

**未修改**: `outbox.ts`（已有 owner filter，本轮未改）、`session-cleanup.ts`（已有 owner 参数）、后端任何文件。

---

## 6. 新增测试

### submission-coordinator.test.ts（+8 tests, 16 total）

| # | 测试 | 覆盖 |
|:--|------|------|
| 1 | `returns no-op result when owner is not provided` | fail-closed |
| 2 | `returns no-op result when owner is empty string` | fail-closed |
| 3 | `passes owner to listPending for scoped query` | 正确传参 |
| 4 | `only submits entries belonging to the current owner` | 回归防护 |
| 5 | `never submits other owner entries with current session` | **安全核心** |
| 6 | `skips entries whose owner does not match (defense-in-depth)` | 双重防护 |
| 7 | `does not submit ownerless legacy entries` | legacy 安全 |
| 8 | `does not auto-bind ownerless entries to current user` | 禁止归属 |
| 9 | `listPending is called with owner for scoped query` | 无全量回退 |

### outbox-owner-isolation.test.ts（7 tests, new file）

| # | 测试 | 覆盖 |
|:--|------|------|
| 1 | `listPending returns only entries matching owner` | A vs B 隔离 |
| 2 | `listPending does not return cross-owner entries` | 零污染 |
| 3 | `listAll returns only requested owner` | 列表隔离 |
| 4 | `listAll returns all when no owner (backward compat)` | 兼容性 |
| 5 | `countAll only counts specified owner` | 计数隔离 |
| 6 | `countPending only counts pending for specified owner` | 计数隔离 |
| 7 | `logout count only shows current user's pending` | 退出统计 |

**结果: 23/23 passed, 0 failed**

---

## 7. 安全证明

### Q1: A 的 Outbox 是否可能在 B 登录后被读取到用于 flush？

**NO。** `runFlush(owner)` 调用 `listPending(owner)`，IndexedDB filter 要求 `e.owner === owner` 精确匹配。B 登录时 owner = "EMP-B"，只返回 EMP-B 的条目。

测试证据: `never submits other owner entries with current session` — EMP-B flush 不触及 EMP-A 条目。

### Q2: A 的 Outbox 是否可能使用 B 当前 session 发请求？

**NO。** 双重防护：(1) `listPending(owner)` 不返回 A 条目；(2) defense-in-depth guard `entry.owner !== owner → skip`。

测试证据: `skips entries whose owner does not match (defense-in-depth)` — 即使 listPending 回归，防御层仍阻止跨用户。

### Q3: owner="" 的旧记录是否会自动归给当前用户？

**NO。** 没有任何代码路径修改 outbox 条目的 owner 字段。owner="" 的记录永远不会被 `listPending("EMP-A")` 返回。

测试证据: `does not auto-bind ownerless entries to current user`。

### Q4: owner="" 的旧记录是否会被自动提交？

**NO。** `listPending(owner)` filter 排除 owner="" 条目 + defense-in-depth guard 跳过不匹配条目。

测试证据: `does not submit ownerless legacy entries`。

### Q5: 退出提示是否只统计当前用户？

**YES。** `getPendingLogoutCount(owner)` → `listAll(owner)` → `.length`。A = 2, B = 3，A 退出只显示 2。

测试证据: `logout count only shows current user's pending`。

### Q6: 切换账号后原用户 pending 是否仍保留？

**YES。** B 的 flush 只读取/删除 B 的条目。A 的条目在 IndexedDB 中保持 PENDING 状态，等待 A 再次登录后自己的 flush 处理。

测试证据: `never submits other owner entries with current session` — A 条目保持 PENDING，不被 B 修改。

---

## 8. 质量门

| 检查 | 结果 |
|------|:--:|
| TypeScript (`npx tsc --noEmit`) | ✅ 0 errors |
| Vitest (`npx vitest run`) | ✅ 302 passed, 62 files, 0 new failures |
| Outbox isolation tests | ✅ 23/23 passed |
| Coordinator tests | ✅ 16/16 passed |
| Acceptance (`pytest tests/acceptance/`) | ✅ 24/24 passed |
| Facade (`pytest tests/modules/`) | ✅ 5/5 passed |
| Ruff (`ruff check .`) | ✅ All checks passed |
| Mypy (`mypy app/`) | ✅ 198 files, 0 errors |

---

## 9. 新增失败

**无。**

---

## 10. 预存失败

| 文件 | 错误 | 状态 |
|------|------|:--:|
| `pwa-cache-policy.test.ts` | `virtual:pwa-register` 未注册 | 预存 |
| `shell-ports/ports_ds.test.ts` | `FileHandle.read` mock 缺失 | 预存 |

与本轮修改无关。

---

## 11. Git 状态

```
 M frontend/apps/web/src/mobile/MobileOutboxPage.tsx
 M frontend/apps/web/src/mobile/session/MobileSessionProvider.tsx
 M frontend/apps/web/src/mobile/sync/SubmissionCoordinator.ts
 M frontend/apps/web/src/mobile/sync/submission-coordinator.test.ts
?? frontend/apps/web/src/mobile/storage/outbox-owner-isolation.test.ts
```

5 文件，未暂存，未提交，未推送。
