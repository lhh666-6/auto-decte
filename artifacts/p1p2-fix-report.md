# 竹丝工序 PWA — P1/P2 修复报告

> **日期**: 2026-07-24
>
> **分支**: `modular-architecture`（commit `45cebf8`）
>
> **范围**: 仅前端，零后端/API/数据库修改

---

## 1. 修改概览

| 维度 | 数值 |
|------|------|
| 修改文件 | 12 个 |
| 新增行数 | +53 |
| 删除行数 | -25 |
| TypeScript | ✅ 0 errors |
| Vitest | ✅ 286 passed（59/61 files） |
| 后端 Acceptance | ✅ 29/29 passed |
| Ruff | ✅ All checks passed |

---

## 2. 逐项修复详情

### P1.7: 主管流程修复（3 文件）

#### Bug: `returnBambooRecord` 缺少 `expected_revision`

**影响**: 后端 `SelectiveReturnRequest` 要求 `expected_revision: int = Field(ge=1)`，前端未传 → 422 错误，主管回退功能完全不可用。

**修复**:
- [mobile_ds.ts:623-634](frontend/packages/api-client/src/mobile_ds.ts#L623)：函数签名新增 `expectedRevision: number` 参数，JSON body 添加 `expected_revision`
- [BambooOperationsPanel.tsx:286](frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx#L286)：调用点传入 `record.revision`

#### 缺失: 主管无法关闭检测异常

**影响**: 后端允许 `INSPECTOR, SUPERVISOR, PLANT_MANAGER` 关闭异常，但前端按钮条件 `role === "INSPECTOR"` 排除了主管。

**修复**: [BambooOperationsPanel.tsx:194](frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx#L194) — 条件改为 `["INSPECTOR", "SUPERVISOR"].includes(role)`

#### 缺失: 签前无异常告警

**修复**:
- [BambooOperationsPanel.tsx:273](frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx#L273) — 主管处理区新增 `error-banner`，列出所有 OPEN 异常
- [BambooStageForm.tsx](frontend/apps/web/src/mobile/bamboo/BambooStageForm.tsx) — 新增可选 prop `unresolvedExceptions`，为 true 时在"通过并签字"按钮上方显示告警

---

### P1.8: 详情页分层（2 文件）

#### 缺失: 无效/已失效提交不可折叠

**影响**: 所有角色的详情页显示全部提交（有效 + 失效），在一个不可折叠的扁平列表中。异常记录多时页面过长。

**修复**: [BambooRecordDetailPage.tsx:93-106](frontend/apps/web/src/mobile/bamboo/BambooRecordDetailPage.tsx#L93)

- 将 `record.submissions` 拆分为 `effectiveSubs` 和 `invalidatedSubs`
- 有效提交仍直接渲染为 `article` 卡片
- 无效提交包裹在 `<details className="bamboo-invalidated-history">` 中，summary 显示 `历史/已失效（N 条）`

**新增 CSS**: [styles.css](frontend/apps/web/src/styles.css)
```css
.bamboo-invalidated-history { margin: 12px 0; }
.bamboo-invalidated-history summary {
  cursor: pointer; color: var(--sub);
  font-size: var(--font-caption); padding: 8px 0;
}
```

---

### P1.9: 离线提交隔离（9 文件）

#### Bug: Outbox 无用户隔离

**影响**: `listAll()` / `listPending()` / `countAll()` 返回所有设备的全部条目。多用户共用设备时数据泄漏。

**修复**:
- [outbox.ts](frontend/apps/web/src/mobile/storage/outbox.ts) — `OutboxEntry` 新增 `owner: string` 字段；`listPending()` / `listAll()` / `countAll()` / `countPending()` 接受可选 `owner` 参数过滤
- [SubmissionCoordinator.ts:46](frontend/apps/web/src/mobile/sync/SubmissionCoordinator.ts#L46) — `enqueue()` 写入 `owner: draftRef?.owner ?? ""`
- [MobileOutboxPage.tsx](frontend/apps/web/src/mobile/MobileOutboxPage.tsx) — 传入 `sessionMetadata?.employee_code`
- [session-cleanup.ts](frontend/apps/web/src/mobile/storage/session-cleanup.ts) — `getPendingLogoutCount(owner?)` 透传
- [MobileProfilePage.tsx](frontend/apps/web/src/mobile/MobileProfilePage.tsx) / [BambooV3ProfilePage.tsx](frontend/apps/web/src/mobile/v3/BambooV3ProfilePage.tsx) — 退出确认传入 `profile?.employee_code`

> **注意**: `SubmissionCoordinator.runFlush()` 的 `listPending()` 调用不传 owner（同步引擎需处理所有未决条目）。

#### Bug: API 失败时 draftCount 归零

**影响**: `BambooV3SubmissionsPage` 的 `loadHistory` 将 `setDraftCount(...)` 放在 `try` 块中。远端 API 失败时 catch 捕获异常，`draftCount` 保持初始值 0，用户看不到本地草稿数量。

**修复**: [BambooV3SubmissionsPage.tsx:21-28](frontend/apps/web/src/mobile/v3/BambooV3SubmissionsPage.tsx#L21) — `setDraftCount(countBambooDrafts(...))` 移入 `finally` 块

---

### P2.11: 含水率输入

**状态**: ✅ 已在 V3 中实现，无需修改。

两个含水率输入位置均已使用 `type="text" inputMode="numeric" pattern="[0-9]*"`：
- [BambooStageForm.tsx:141-143](frontend/apps/web/src/mobile/bamboo/BambooStageForm.tsx#L141)
- [BambooTaskListPage.tsx:487-489](frontend/apps/web/src/mobile/bamboo/BambooTaskListPage.tsx#L487)

---

## 3. 质量门

| 检查项 | 结果 |
|--------|:--:|
| TypeScript (`npx tsc --noEmit`) | ✅ 0 errors |
| Vitest (`npx vitest run`) | ✅ 286 passed（2 预存 PWA 失败） |
| Acceptance (`pytest tests/acceptance/`) | ✅ 24/24 passed |
| Facade (`pytest tests/modules/`) | ✅ 5/5 passed |
| Ruff (`ruff check .`) | ✅ All checks passed |
| Mypy (`mypy app/`) | ✅ 198 files, 0 errors |

---

## 4. 未完成的 P1/P2 项（handoff 标记为非阻塞）

| 项 | 状态 | 原因 |
|:--|:--:|------|
| P1.7 主管逐工序独立评价 | 延后 | 需要 API schema 变更 + 迁移 |
| P1.8 详情页角色分层过滤 | 延后 | 需要 DTO + 权限模型设计 |
| P1.10 厂长人员配置 | 延后 | 功能基本可用，hardcoded 枚举属架构演进 |
| P2.12 真实浏览器验收 | 待做 | 需要 Playwright 测试体系搭建 |

---

## 5. Git 状态

```
modular-architecture @ 45cebf8
fix(mobile): P1/P2 bug fixes — supervisor, outbox, detail, offline

12 files changed, 53 insertions(+), 25 deletions(-)
未被跟踪，未推送
```
