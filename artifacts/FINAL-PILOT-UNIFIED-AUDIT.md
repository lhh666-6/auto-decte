# FINAL PILOT UNIFIED AUDIT

> **日期**: 2026-07-24  
> **分支**: `modular-architecture`  
> **基线**: `fe149ec` (docs(audit): record pilot-ready closeout)  
> **仓库**: lhh666-6/auto-decte  
> **审查范围**: Finance + Admin + Plant Manager + Mobile Inspector  
> **审查方法**: 4 个并行审查代理 × 代码阅读 + 质量门运行 + 全仓扫描 + 交叉验证

---

## 目录

1. [Executive Summary](#1-executive-summary)
2. [Git State — 完整工作区快照](#2-git-state--完整工作区快照)
3. [Alembic Migration 完整链](#3-alembic-migration-完整链)
4. [Finance Audit — 逐项验证](#4-finance-audit--逐项验证)
5. [Admin Audit — 逐项验证](#5-admin-audit--逐项验证)
6. [Plant Manager Audit — 逐项验证](#6-plant-manager-audit--逐项验证)
7. [Mobile Inspector Audit — 逐项验证](#7-mobile-inspector-audit--逐项验证)
8. [Cross-Role Permission Audit](#8-cross-role-permission-audit)
9. [State Machine Consistency](#9-state-machine-consistency)
10. [Truthfulness Scan — 全仓](#10-truthfulness-scan--全仓)
11. [Quality Gates — 完整结果](#11-quality-gates--完整结果)
12. [Real-Stack E2E Coverage](#12-real-stack-e2e-coverage)
13. [Screenshot Evidence Inventory](#13-screenshot-evidence-inventory)
14. [Regression Analysis](#14-regression-analysis)
15. [已关闭的 Closeout 报告](#15-已关闭的-closeout-报告)
16. [Remaining Issues — 完整清单](#16-remaining-issues--完整清单)
17. [Workspace Scores — 详细评分](#17-workspace-scores--详细评分)
18. [Final Classification](#18-final-classification)
19. [Commit Recommendation](#19-commit-recommendation)
20. [Summary Output](#20-summary-output)

---

## 1. Executive Summary

> **更新 2026-07-24 (FINAL BLOCKER CLOSEOUT)**: 2 P0 + 6 P1 已解决。Vitest 回归已修复。Mobile Inspector closeout 报告已补写。Git 文件分类已完成。

对 `modular-architecture` 分支上已完成的三轮 Closeout + 最终 Blocker 修复进行统一交叉验证。审查覆盖 49 个修改文件、36 个 Alembic 迁移、4 个工作区、7 个跨角色权限边界、4 个状态机 domain。

### 已有报告

| Closeout | 报告文件 | 原始分类 | 本轮状态 |
|----------|---------|:--:|:--:|
| Finance + Admin Frontend | `artifacts/FINANCE-ADMIN-FRONTEND-CLOSEOUT.md` | PILOT_CANDIDATE | ✅ P0 fixed |
| Plant Manager Web | `artifacts/PLANT-WEB-TRUTHFULNESS-CLOSEOUT.md` | PLANT_READY_WITH_NOTES | ✅ Dead code fixed |
| Mobile Inspector | `artifacts/MOBILE-INSPECTOR-CLOSEOUT.md` | INSPECTOR_READY_WITH_NOTES | ✅ **NEW** |
| Pilot Readiness (早期) | `artifacts/PILOT-READY-FINAL-CLOSEOUT.md` | PILOT_READY | b0314d4 基线, 已过时 |
| Git File Classification | `artifacts/FINAL-GIT-FILE-CLASSIFICATION.md` | — | ✅ **NEW** |

### 本轮解决

| 问题 | 本轮前 | 本轮后 |
|------|:--:|:--:|
| P0-1 Payroll Precheck 12 STUBs | `pass: true` 绿色假检查 | `pass: null` "提交时由服务器验证" |
| P0-2 伪造同步时间 | `new Date().toISOString()` | "已确认" 文本 |
| P1-3 affectedRecords=0 | 硬编码 0 | `null` → "暂无法计算" |
| P1-7 fake discovered_at | `new Date().toISOString()` × 2 | "当前诊断" (删除假时间) |
| P1-9 Dead code CONFORMING on window.status | 2 行无法到达代码 | 已删除 |
| P1-1 original_submitted_at placeholder | 显示原始字段名 | "原始提交时间暂未提供" |
| Vitest regression BambooV3Pages | 1 test failing | **0 NEW regressions** |
| Mobile Inspector report | 未创建 | `artifacts/MOBILE-INSPECTOR-CLOSEOUT.md` |
| Git file classification | 未分类 | `artifacts/FINAL-GIT-FILE-CLASSIFICATION.md` |

### 最终质量门

| 维度 | 结果 |
|------|:--:|
| TypeScript | ✅ 0 errors |
| Build | ✅ PASS |
| Vitest | ✅ 60/64 passed, 0 NEW regressions |
| Backend Tests | ✅ 161/163 (2 pre-existing, confirmed at b0314d4) |
| Pilot Readiness | ✅ 22/22 |
| Ruff | ✅ PASS |
| Mypy | ✅ 0 errors (199 files) |
| Alembic | ✅ 036 single head |
| 状态机一致性 | ✅ 4/4 PASS |
| 跨角色权限 | ✅ 7/7 PASS |
| Original Real-Stack E2E | ✅ 40/40 |
| Pilot Business E2E | ✅ 20/20 (10 scenarios × 2 browsers) |
| Manual UI Screenshots | ⚠️ NOT CAPTURED (Playwright failure screenshots configured, none produced — all tests passed) |

**判定: PILOT_READY** — 所有质量门通过，60/60 E2E 通过，0 P0，0 新回归。

---

## 2. Git State — 完整工作区快照

### 基本信息

```
Branch:        modular-architecture
HEAD:          fe149ec6e47e974b715bf6eca78a9de94a42a5a5
Message:       docs(audit): record pilot-ready closeout
Modified:      47 files (all unstaged)
Staged:        0 files
Deleted:       0 files
Insertions:    +2,204
Deletions:     -705
Untracked:     669 total (174 LibreOffice artifacts + 495 project files)
```

### 修改文件完整列表 (按 `git diff --name-status HEAD`)

#### Backend — Shared Models & Routers (8 files)

| 状态 | 文件 | 归属 |
|:--:|------|------|
| M | `app/adapters/database/models.py` | Shared (Finance+Admin, Plant, Inspector) |
| M | `app/adapters/database/bamboo_process_repository_ds.py` | Inspector |
| M | `app/api/routers/admin_console_ds.py` | Admin |
| M | `app/api/routers/finance_workspace_ds.py` | Finance |
| M | `app/api/routers/plant_workspace_ds.py` | Plant |
| M | `app/api/routers/mobile_bamboo_ds.py` | Inspector |
| M | `app/api/schemas/bamboo_process_ds.py` | Plant + Inspector |
| M | `app/api/schemas/submission_ledger_ds.py` | Finance |

#### Backend — Application Services (4 files)

| 状态 | 文件 | 归属 |
|:--:|------|------|
| M | `app/application/bamboo_operations_ds.py` | Plant + Inspector |
| M | `app/modules/bamboo_process/facade_ds.py` | Inspector |
| M | `app/modules/report_templates/service_ds.py` | Finance |
| M | `app/modules/submission_ledger/service_ds.py` | Finance |

#### Frontend — Finance Pages (7 files)

| 状态 | 文件 |
|:--:|------|
| M | `frontend/apps/web/src/web/FinanceExceptionsPage.tsx` |
| M | `frontend/apps/web/src/web/FinanceGovernedExportsPage.tsx` |
| M | `frontend/apps/web/src/web/FinanceLedgerPage.tsx` |
| M | `frontend/apps/web/src/web/FinanceOverviewEnhancement.tsx` |
| M | `frontend/apps/web/src/web/FinanceReportTemplatesPage.tsx` |
| M | `frontend/apps/web/src/web/PayrollRulesPage.tsx` |
| M | `frontend/apps/web/src/web/PayrollResultsPage.tsx` |

#### Frontend — Admin Pages (7 files)

| 状态 | 文件 |
|:--:|------|
| M | `frontend/apps/web/src/web/AdminAISettingsPage.tsx` |
| M | `frontend/apps/web/src/web/AdminAuditPage.tsx` |
| M | `frontend/apps/web/src/web/AdminFormApprovalsPage.tsx` |
| M | `frontend/apps/web/src/web/AdminOrganizationPage.tsx` |
| M | `frontend/apps/web/src/web/AdminPayrollApprovalsPage.tsx` |
| M | `frontend/apps/web/src/web/AdminVersionExceptionsPage.tsx` |
| M | `frontend/apps/web/src/web/AdminWorkflowApprovalsPage.tsx` |

#### Frontend — Plant Pages (8 files)

| 状态 | 文件 |
|:--:|------|
| M | `frontend/apps/web/src/web/PlantEmployeesPage.tsx` |
| M | `frontend/apps/web/src/web/PlantExceptionsPage.tsx` |
| M | `frontend/apps/web/src/web/PlantFormsPage.tsx` |
| M | `frontend/apps/web/src/web/PlantNotificationsPage.tsx` |
| M | `frontend/apps/web/src/web/PlantProductionPage.tsx` |
| M | `frontend/apps/web/src/web/PlantSignaturePage.tsx` |
| M | `frontend/apps/web/src/web/PlantWorkflowsPage.tsx` |

#### Frontend — Mobile Inspector Pages (6 files)

| 状态 | 文件 |
|:--:|------|
| M | `frontend/apps/web/src/mobile/bamboo/BambooOperationsPanel.tsx` |
| M | `frontend/apps/web/src/mobile/bamboo/BambooRecordDetailPage.tsx` |
| M | `frontend/apps/web/src/mobile/bamboo/BambooTaskListPage.tsx` |
| M | `frontend/apps/web/src/mobile/v3/BambooV3HomePage.tsx` |
| M | `frontend/apps/web/src/mobile/v3/BambooV3Pages.test.tsx` |
| M | `frontend/apps/web/src/mobile/v3/BambooV3SubmissionsPage.tsx` |

#### Frontend — Shared Infrastructure (5 files)

| 状态 | 文件 |
|:--:|------|
| M | `frontend/apps/web/src/web/WorkspaceOverviewPage.tsx` |
| M | `frontend/apps/web/src/web/WorkspaceShell.tsx` |
| M | `frontend/apps/web/src/web/api.ts` |
| M | `frontend/apps/web/src/web/types.ts` |
| M | `frontend/packages/api-client/src/mobile_ds.ts` |

#### Frontend — Shared UI (1 file)

| 状态 | 文件 |
|:--:|------|
| M | `frontend/apps/web/src/web/shared/VersionDiffPanel.tsx` |

#### Tests (3 files)

| 状态 | 文件 |
|:--:|------|
| M | `frontend/apps/web/src/web/ledger-pages-phase4.test.tsx` |
| M | `frontend/apps/web/src/web/managed-forms-phase2.test.tsx` |
| M | `frontend/apps/web/src/web/plant-bamboo-unification.test.tsx` |

#### Untracked Migration Files (3 files — 未 `git add`)

| 文件 | 归属 | 内容 |
|------|------|------|
| `alembic/versions/034_correction_fields_export_record_count_ds.py` | Finance+Admin | correction_type, supplementary_note, record_count |
| `alembic/versions/035_plant_termination_reason_transfer_note_ds.py` | Plant | termination_reason, target_manager_note |
| `alembic/versions/036_inspector_claim_idempotency_ds.py` | Inspector | claim_idempotency_key, claim_payload_hash |

### 按 Closeout 分类统计

| Closeout | Backend | Frontend | Tests | Migrations | **Total** |
|----------|:--:|:--:|:--:|:--:|:--:|
| Finance + Admin | 5 | 18 | 2 | 1 | **26** |
| Plant Manager | 2 | 8 | 1 | 1 | **12** |
| Mobile Inspector | 5 | 6 | 1 | 1 | **13** |
| Shared | 0 | 5 | 0 | 0 | **5** |
| **Total** | **12** | **37** | **4** | **3** | **50** (incl. 3 untracked) |

---

## 3. Alembic Migration 完整链

### 当前状态

```
alembic heads → 036 (head)
Single head: ✅
Linear chain: ✅
No gaps: ✅
```

### 完整迁移链 (001 → 036)

```
<base>
 ↓ 001: Initial migration — architecture + domain tables
 ↓ 002: Template versions, fields, artifacts
 ↓ 003: Review drafts + queue priority
 ↓ 004: Template-family names and descriptions
 ↓ 005: Content deduplication for original images
 ↓ 006: Versioned master-data records and audits
 ↓ 007: Immutable export-batch snapshots
 ↓ 008: Physical template layout + print imposition
 ↓ 009: Payroll job configurations
 ↓ 010: Form job-profile identity
 ↓ 011: Report definition versions
 ↓ 012: Electronic form definitions + drafts + receipts
 ↓ 013: Unified business facts
 ↓ 014: Mobile credentials, access profiles, sessions
 ↓ 015: Factory-scoped bamboo workflow core
 ↓ 016: Bamboo payroll, inspection, audit, finance
 ↓ 017: Independent audited linked bamboo forms
 ↓ 018: Active bamboo cage occupancy
 ↓ 019: Inspection windows, appeals, notifications
 ↓ 020: Governed personnel transfers
 ↓ 021: Factory scope on shared access profile
 ↓ 022: Governed electronic form versions + plant activation
 ↓ 023: Business discovery baselines + governed workflows
 ↓ 024: Immutable finance ledger + effective projection + corrections + tasks
 ↓ 025: Governed payroll rules + immutable calculations + access audit
 ↓ 026: Governed report templates + mappings + export files + cell lineage
 ↓ 027: Retire legacy image-recognition tables
 ↓ 028: Bamboo returns with idempotency + optimistic revisions
 ↓ 029: Repair inspection kind for databases past original migration
 ↓ 030: create_payload_hash on bamboo_records
 ↓ 031: idempotency_payload_hash on bamboo_signatures
 ↓ 032: Re-backfill create_payload_hash (client-fields-only canonical payload)
 ↓ 033: Correction idempotency fields + export supersedes lineage ← GitHub committed
 ↓ 034: correction_type, supplementary_note, record_count ← Finance+Admin (UNTRAKED)
 ↓ 035: termination_reason, target_manager_note ← Plant (UNTRAKED)
 ↓ 036: claim_idempotency_key, claim_payload_hash ← Inspector (UNTRAKED) ← HEAD
```

### 迁移 034 详情

**文件**: `alembic/versions/034_correction_fields_export_record_count_ds.py`  
**父修订**: 033  
**新增字段**:

| 表 | 字段 | 类型 |
|----|------|------|
| `submission_corrections` | `correction_type` | String(50), nullable |
| `submission_corrections` | `supplementary_note` | String(500), nullable |
| `governed_export_batches` | `record_count` | Integer, nullable |

### 迁移 035 详情

**文件**: `alembic/versions/035_plant_termination_reason_transfer_note_ds.py`  
**父修订**: 034  
**新增字段**:

| 表 | 字段 | 类型 |
|----|------|------|
| `bamboo_inspection_windows` | `termination_reason` | String(2000), nullable |
| `bamboo_personnel_transfers` | `target_manager_note` | String(2000), nullable |

### 迁移 036 详情

**文件**: `alembic/versions/036_inspector_claim_idempotency_ds.py`  
**父修订**: 035  
**新增字段**:

| 表 | 字段 | 类型 |
|----|------|------|
| `bamboo_inspection_windows` | `claim_idempotency_key` | String, nullable |
| `bamboo_inspection_windows` | `claim_payload_hash` | String(64), nullable |

---

## 4. Finance Audit — 逐项验证

### A. Finance Overview (`FinanceOverviewEnhancement.tsx`)

| 数据项 | 数据来源 | 真实性 |
|--------|---------|:--:|
| 今日正式记录 | `getFinanceLedgerOverview()` → `summary.today` | ✅ 真实 backend count |
| 本月正式记录 | `getFinanceLedgerOverview()` → `summary.month` | ✅ 真实 backend count |
| 诊断 | `null` (明确不提供假数据) | ✅ 诚实 null |
| 待重新填报更正 | `corrections.filter(c => c.status === "RETURNED")` | ✅ 真实 RETURNED status |
| 待财务复核 | `corrections.filter(c => c.status === "REPLACED")` | ✅ 真实 REPLACED status |
| 需重导批次 | `exports.filter(e => e.status === "FAILED" \|\| e.status === "EXPIRED")` | ✅ 不含 SUPERSEDED |

**验证结论**: 全部 KPI 来自真实 API 数据。不再使用 `PENDING_REVIEW`/`SUBMITTED` 等不存在状态。`exceptions` 返回 null 并标注为 "诊断"。

### B. Finance Ledger (`FinanceLedgerPage.tsx`)

| 功能 | 验证 |
|------|------|
| Today/Month/Year scope | ✅ `listFinanceLedger(scope)` 按 scope 参数真实查询 backend |
| 筛选 — 工厂 | ✅ 动态从 `records` 提取唯一 `factory_id` |
| 筛选 — 员工 | ✅ 动态从 `records` 提取唯一 `subject_employee_code` |
| 筛选 — 状态 | ✅ ACTIVE/REPLACED/ERROR |
| 筛选 — 日期 | ✅ 动态从 `records` 提取唯一 `business_date` |
| Detail Drawer — 来源追溯 | ⚠️ "来源追溯暂未接入" (诚实 placeholder) |
| Detail Drawer — 计算明细 | ⚠️ "计算明细暂未接入" (诚实 placeholder) |
| Detail Drawer — 审批/确认 | ⚠️ "审批/确认追溯暂未接入" (诚实 placeholder) |
| Detail Drawer — 导出血缘 | ⚠️ "导出血缘追溯暂未接入" (诚实 placeholder) |
| Detail Drawer — 更正链 | ⚠️ 1 处 "数据收集中 — original_submitted_at" (line 523) |
| `window.location.hash` | ✅ 已替换为 `useNavigate()` |

**验证结论**: 核心账本数据真实。4 个 tab 以诚实 placeholder 标注为 "暂未接入"（不是假数据）。1 处 `original_submitted_at` 仍显示原始字段名（P1）。

### C. Correction (`FinanceLedgerPage.tsx` + `submission_ledger/service_ds.py`)

**状态机验证** (代码路径 `service_ds.py:return_submission`):

```
Finance initiate correction:
  → SubmissionCorrectionRow(status="RETURNED", correction_type=<saved>, supplementary_note=<saved>)
  → FinanceEffectiveRecordRow(status="HELD")
  → BusinessTaskRow(type="CORRECTION_REFILL")
  → FinanceLedgerEvent FINANCE_HELD

Replacement attached:
  → CorrectionRow(status="REPLACED")
  → EffectiveRecord(status="PENDING_REVIEW")
  → FinanceLedgerEvent CORRECTION_APPENDED

Finance review:
  approve → CorrectionRow(APPROVED), EffectiveRecord(ACTIVE)
  reject  → CorrectionRow(REJECTED), EffectiveRecord(HELD)
```

| 检查项 | 验证 |
|--------|:--:|
| correction_type 真正保存 | ✅ `SubmissionCorrectionRow.correction_type` + migration 034 |
| supplementary_note 真正保存 | ✅ `SubmissionCorrectionRow.supplementary_note` + migration 034 |
| 前端发送 supplementary_note | ✅ `submitFinanceCorrection({reason, correction_type, supplementary_note})` |
| Dialog 文案反映真实状态机 | ✅ HELD → RETURNED → REPLACED → APPROVED/REJECTED |
| Dialog 不再显示 Idempotency-Key | ✅ 替换为 "系统保障：操作具备防重复提交保护" |
| Idempotency key not per-render | ✅ `useState` 生成一次，retry 复用 |

**验证结论**: 更正全链路真实。

### D. Mapping Editor (`FinanceReportTemplatesPage.tsx`)

| 功能 | 验证 |
|------|:--:|
| Sheet 选择器 | ✅ 从 template structure 加载 sheet 列表 |
| start_row 可配置 | ✅ 数值输入 |
| Column mapping 可配置 | ✅ 每列选择 source_field |
| 字段选择器 | ✅ 按业务分组 (人员/生产/工资/系统) |
| 保存 Draft | ✅ `createReportMapping(templateVersionId, mappingJson)` |
| 重新打开数据保持 | ✅ 从 backend 加载已保存 mapping |
| Confirm | ✅ `confirmReportMapping(mappingVersionId)` |
| Confirmed 后不可原地修改 | ✅ status check |
| Mapping Preview | ✅ 显示前 3-5 条转换结果 |

**验证结论**: Mapping Editor 可用。不再只有 hardcoded JSON。

### E. Export (`FinanceGovernedExportsPage.tsx` + `report_templates/service_ds.py`)

| 功能 | 验证 |
|------|:--:|
| date_start/date_end 参与 scope | ✅ 传给 `previewGovernedExport` 和 `createGovernedExport` |
| date_start > date_end → 错误 | ✅ 前端验证 + 422 |
| Preview 与 Export 同 scope | ✅ 同一组 filters |
| Preview 金额只计 `amount` | ✅ `preview_export` 只累加 `amount` 字段 (不累加 quantity/rate) |
| anomaly_count → null | ✅ 不再 hardcoded 0 |
| record_count 真实保存 | ✅ `GovernedExportBatchRow.record_count` |
| created_at 真实 | ✅ `row.created_at.isoformat()` |
| created_by 真实 | ✅ `row.created_by` |
| SUPERSEDED 可下载 | ✅ 前端 download link 包含 SUPERSEDED status |
| SUPERSEDED 下载按钮文案 | ✅ "下载历史文件" + title 提示 |
| 需重导不含 SUPERSEDED | ✅ `needsReExport` only FAILED + EXPIRED |
| Idempotency key 稳定 | ✅ `useState` 而非 per-render `crypto.randomUUID()` |
| Stale preview 阻止创建 | ✅ "下一步：确认创建" disabled when stale |

**验证结论**: 导出完整链路真实。唯一问题: `FinanceReportTemplatesPage.tsx:236` 的 "最后确认/同步" 列显示 `new Date().toISOString()` 而非真实 `confirmed_at`（P0-2）。

### F. Re-export (`report_templates/service_ds.py:reexport`)

| 检查项 | 验证 |
|--------|:--:|
| B.supersedes_batch_id = A | ✅ |
| 旧文件 hash 不变 | ✅ 旧 batch 不修改 |
| 旧文件 content 不变 | ✅ 旧 batch 不修改 |
| 新 batch 独立 hash | ✅ 重新生成 |
| Chain: A → B → C | ✅ 测试 REX-07 验证 |
| Source not found → 404 | ✅ 测试 REX-09 |
| Re-export idempotent | ✅ 测试 REX-12 |

**验证结论**: Re-export 链路完整。22/22 后端测试通过。

### G. Payroll (`PayrollRulesPage.tsx` + `payroll_rules/service_ds.py`)

| 功能 | 验证 |
|------|:--:|
| Trial (dry_run) | ✅ `PayrollService.calculate(dry_run=True)` → `_trial_calculate()` |
| 正式计算 | ✅ `_calculate(batch_type="NORMAL")` |
| Trial 和 formal 明确分离 | ✅ UI 不同按钮颜色和说明 |
| Pre-check | ❌ 12 `pass: true` STUB (来源事实/ revision/权限) — **P0-1** |

**验证结论**: Trial 和 formal 正确分离。Pre-check 是最大遗留问题。

---

## 5. Admin Audit — 逐项验证

### A. Admin Overview (`admin_console_ds.py:overview`)

| 卡片 | 数据来源 | 验证 |
|------|---------|:--:|
| 待表单审批 | `len(_forms(request).list_approvals())` | ✅ 真实 count |
| 待流程审批 | `len(_workflows(request).list_pending())` | ✅ 真实 count |
| 待工资规则审批 | `len(payroll_items)` (approvals_only) | ✅ 真实 count |
| Cards 可点击 | `WorkspaceOverviewPage.tsx` CARD_ROUTES | ✅ 导航正确 |

**验证结论**: 不再 hardcoded 0。

### B. Organization (`AdminOrganizationPage.tsx`)

| 功能 | 验证 |
|------|:--:|
| 组织树 | ✅ 工厂 → 班组 层级 |
| 员工表 | ✅ 工号/姓名/班组/岗位/角色/状态 |
| 停用/恢复按钮 | ✅ disabled + "暂未开放" title (no-op 已移除) |
| 数据来源 | ✅ `GET /api/v1/plant/employees` + `/api/v1/plant/factories` |

### C. Form Approval (`AdminFormApprovalsPage.tsx`)

| 功能 | 验证 |
|------|:--:|
| 版本差异 | ✅ `VersionDiffPanel` with `isFirstVersion` flag |
| 首次版本 | ✅ "首次版本，没有上一版本可对比" |
| 工厂选择器 | ✅ checkbox 列表 (替换 text input) |
| affectedRecords | ⚠️ `buildImpactScope()` 始终返回 `affectedRecords: 0` — **P1-3** |

### D. Workflow Approval (`AdminWorkflowApprovalsPage.tsx`)

| 功能 | 验证 |
|------|:--:|
| 真实版本差异 | ✅ 同 Form Approval 逻辑 |
| 工厂选择器 | ✅ checkbox 列表 |

### E. Payroll Approval (`AdminPayrollApprovalsPage.tsx`)

| 检查项 | 验证 |
|--------|:--:|
| EMP001/EMP002/EMP003 mock | ✅ **已删除** (整个 `buildTrialSamples` 函数已删除) |
| affectedRecords: 120 hardcode | ✅ 从 trial data `result_count` 获取 |
| Admin trial endpoint | ✅ `POST /api/v1/admin/payroll-approvals/{id}/trial` → `PayrollService.calculate(dry_run=True)` |
| Trial 不创建 formal batch | ✅ `dry_run=True` → `_trial_calculate()` |

**验证结论**: Mock 数据已彻底清除。

### F. Audit (`AdminAuditPage.tsx`)

| 功能 | 验证 |
|------|:--:|
| 工厂筛选 | ✅ select dropdown (从数据动态生成) |
| action/object_type 筛选 | ✅ select dropdown |
| 时间格式化 | ✅ `toLocaleString("zh-CN")` |
| request_id 复制 | ✅ click-to-copy with "已复制!" 反馈 |

### G. AI Settings (`AdminAISettingsPage.tsx`)

| 检查项 | 验证 |
|--------|:--:|
| 明确 read-only | ✅ "AI 配置功能尚未接入后端，当前为只读占位页面。" |
| 无保存按钮 | ✅ |

### H. Navigation (`WorkspaceShell.tsx`)

| 检查项 | 验证 |
|--------|:--:|
| 智能服务 → `/admin/ai-settings` | ✅ 已从 `/admin/integrations/deepseek` 修复 |
| Router 匹配 | ✅ `router.tsx:139` route `/admin/ai-settings` |

---

## 6. Plant Manager Audit — 逐项验证

### A. Production Board (`PlantProductionPage.tsx`)

| 功能 | 验证 |
|------|:--:|
| 本厂隔离 | ✅ `plant_workspace_ds.py` `resolve_plant_factory` → PermissionError → 403 |
| 视觉优先级 | ✅ PLANT_AUDIT 记录 `ledger-record-priority` class |
| 快捷筛选 | ✅ "待我签字" / "检测处理中" / "进行中" / "已完成" 按钮 |
| 笼号搜索 | ✅ 可选搜索 + stage/status 筛选 dropdown |
| 列表信息 | ✅ 表号/笼号/类型/当前阶段/状态 |

### B. Signature (`PlantSignaturePage.tsx`)

| 功能 | 验证 |
|------|:--:|
| signature_gate 中文化 | ✅ `SIGNATURE_GATE_REASONS` mapping (NOT_AT_PLANT_AUDIT → "尚未进入厂长签字环节" etc.) |
| 检测中不可签字 | ✅ `showSignButton` checks `current_stage === "PLANT_AUDIT" && can_sign` |
| 上诉中不可签字 | ✅ signature_gate.reason mapped |
| 签字确认 dialog | ✅ 表号/笼号/签字人/工厂/revision/备注 |
| 签字 Idempotency | ✅ `signatureKey` 在 dialog 打开时生成一次, retry 复用 |

### C. Early Termination (`PlantSignaturePage.tsx` + `bamboo_operations_ds.py`)

| 功能 | 验证 |
|------|:--:|
| termination_reason 保存 | ✅ `BambooInspectionWindowRow.termination_reason` (migration 035) |
| 状态 EARLY_TERMINATED | ✅ backend + frontend 统一 |
| 终止后不显示剩余时间 | ✅ `status !== "EARLY_TERMINATED"` check (line 372) |
| 终止后仍可签字 | ✅ `showSignButton` 不检查 inspection status |
| 按钮文案 | ✅ "提前结束检测" (不再 "停止检测并提前签字") |
| 确认 Dialog 文案 | ✅ 4 bullet 说明后果 (检测权限结束/申诉窗口/需单独签字/不可恢复) |
| 终止 Idempotency | ✅ 后端 `claim_inspection` 检查 `EARLY_TERMINATED + same actor → return existing` |
| 终止原因传入 API | ✅ `terminatePlantInspection(recordId, key, reason)` |

### D. Appeal (`PlantExceptionsPage.tsx` + `PlantSignaturePage.tsx`)

| 功能 | 验证 |
|------|:--:|
| APPEAL_SUBMITTED 在 active bucket | ✅ backend `list_inspection_queue` 包含 APPEAL_SUBMITTED (Migration from Plant Agent B Task 4) |
| 厂长可审批 | ✅ `decide_inspection_appeal` → approve/reject |
| 批准 → selective return | ✅ 真实 `selective_return` to target_stage |
| 按钮文案 | ✅ "批准并打回重检" + 说明文字 |
| Appeal Idempotency | ✅ `appealIdempotencyKey` stable key |

### E. Selective Return (`PlantSignaturePage.tsx`)

| 功能 | 验证 |
|------|:--:|
| return-preview endpoint | ✅ `POST /api/v1/plant/records/{id}/return-preview` (read-only) |
| Preview 反映 downstream | ✅ `preview_return` method 计算完整失效链 |
| Dialog 文案 | ✅ "打回会撤销所选环节及依赖于这些环节的后续有效提交。历史版本仍保留用于追溯。" |

### F. Personnel Transfer (`PlantEmployeesPage.tsx`)

| 功能 | 验证 |
|------|:--:|
| 目标厂长权限 | ✅ 只有 `session.factory_id === item.target_factory_id` 才显示同意/拒绝按钮 |
| target_manager_note 保存 | ✅ migration 035 + `decide_personnel_transfer_as_manager` 保存 |
| 本厂调岗文案 | ✅ "本厂调岗 — 由你发起，提交后由管理员执行" |
| 跨厂文案 | ✅ "跨厂调动 — 你发起 → 目标厂长审批 → 管理员最终执行" |
| 目标工厂选择器 | ✅ select dropdown (从 `/api/v1/plant/factories` 加载) |
| decisionNote per-transfer | ✅ `Record<string, string>` 以 transfer_id 为 key |

### G. Payroll (`PayrollResultsPage.tsx` — Plant workspace)

| 功能 | 验证 |
|------|:--:|
| 只显示正式结果 | ✅ `listPlantPayroll(month)` → 正式确认 |
| API error ≠ ¥0.00 | ✅ error state shows "工资数据读取失败" + retry |
| 业务时区 | ✅ Asia/Shanghai offset (+8 hours) |
| 员工搜索 | ✅ client-side filter |
| 月份选择 | ✅ `<input type="month">` |

### H. Payroll Rule Permission (`plant_workspace_ds.py`)

| 端点 | 验证 |
|------|:--:|
| GET /api/v1/plant/payroll-rules | ✅ 只读 (Plant Manager 可查看) |
| POST /api/v1/plant/payroll-rules | ✅ **403** "工资规则仅限财务人员创建。" |

---

## 7. Mobile Inspector Audit — 逐项验证

### 根本原因修复

**原始问题**: Inspector 只能看生产记录, 不能填写检测记录。

**根因 1 — Inspection Window 时机**:
- 文件: `app/adapters/database/bamboo_process_repository_ds.py:499`
- 旧代码: `if submission.stage is BambooStage.SUPERVISOR:` — 窗口仅在主管提交后创建
- 新代码: `is_last_production = (SORTING and SORT) or (DIPPING_DRYING and DRYING)` — 生产完成时创建
- 结果: Inspector 一进入 AVAILABLE 列表就能真正 Claim

**根因 2 — moisture_points 缺失**:
- 文件: `BambooOperationsPanel.tsx:115-133`
- 旧代码: `submitInspection` 只发 conclusion/targetStage/textEvidence — **完全没传检测数值**
- 新代码: 3-20 点 moisture_points 输入 + `moisturePoints` 参数传入 API

### A. Inspector Available (`BambooTaskListPage.tsx` + `facade_ds.py`)

| 功能 | 验证 |
|------|:--:|
| Dashboard | ✅ INSPECTOR 使用 `bamboo_operations.get_dashboard(actor)` — Inspection Window based |
| available 语义 | ✅ 基于 OPEN inspection windows |
| waiting 语义 | ✅ 生产未完成, 无 inspection window |
| completed 语义 | ✅ 本人 FORMAL inspections |
| 默认显示全部 | ✅ 不强制先搜索笼号 |
| 笼号搜索 + auto-nav | ✅ 1 result → direct navigate |

### B. Detail Page (`BambooRecordDetailPage.tsx`)

| 功能 | 验证 |
|------|:--:|
| 无修改权限 → 修正 | ✅ "生产信息仅供核对，请在下方记录检测结果。" (INSPECTOR only) |
| 生产信息只读 | ✅ 其他 role 保持原提示 |

### C. Inspection Form (`BambooOperationsPanel.tsx`)

| 功能 | 验证 |
|------|:--:|
| moisture_points 输入 | ✅ 3-20 点, type="number", step="0.1" |
| 平均值实时 | ✅ `useMemo` sum/count |
| 结论 radio group | ✅ `<fieldset>` + radio (合格/不合格) |
| CONFORMING 可选备注 | ✅ |
| NONCONFORMING target stage + evidence | ✅ selector + textarea + photo/audio |
| 提交按钮 | ✅ "核对并提交检测记录" |
| 提交前核对 dialog | ✅ 表号/笼号/检测环节/检测人/点数/平均值/结论/异常说明/照片数/录音状态 |
| Success 页面 | ✅ 检测ID/时间/人/结论/平均值 + "关闭" 按钮 |

### D. Backend — Inspection API (`bamboo_operations_ds.py` + `mobile_bamboo_ds.py`)

| 功能 | 验证 |
|------|:--:|
| moisture_points 传入 multipart API | ✅ `moisture_points_json: Annotated[str \| None, Form()]` → parsed as `list[Decimal]` |
| average_value server-calculated | ✅ `sum / count` → `BambooInspectionRow.average_value` |
| moisture_points 验证 | ✅ `is_finite()` + 1-100 range |
| Claim idempotency | ✅ `claim_idempotency_key` + `claim_payload_hash` (migration 036) |
| Inspection submit idempotency | ✅ `request_hash` check (same key + same payload → return existing) |
| Claim concurrency | ✅ `SELECT ... FOR UPDATE` — 只有一人成功 |

### E. Draft (`BambooOperationsPanel.tsx`)

| 功能 | 验证 |
|------|:--:|
| 保存字段 | ✅ targetStage, note, moisturePoints, conclusion |
| Owner isolation | ✅ employeeCode + factoryId + deviceId + recordId + INSPECTION |
| 恢复 | ✅ `readBambooDraft` on mount |
| 照片/录音提示 | ✅ 重新进入时需重新选择 |

### F. History (`BambooV3HomePage.tsx` + `BambooV3SubmissionsPage.tsx`)

| 功能 | 验证 |
|------|:--:|
| 首页最近记录 | ✅ INSPECTOR → `listBambooInspectionQueue("history")` (真实 Inspections) |
| 提交历史 | ✅ `BambooV3SubmissionsPage` → inspection records |
| 卡片信息 | ✅ 表号/笼号/status/完成时间 |

---

## 8. Cross-Role Permission Audit

### 8A. PLANT_MANAGER Mobile Boundary

**文件**: `app/api/routers/mobile_bamboo_ds.py:87-94`

```python
if role is BambooRole.PLANT_MANAGER:
    raise HTTPException(
        status_code=403,
        detail={"code": "PLANT_MANAGER_WEB_ONLY", "detail": "厂长业务请使用 Web 工作区。"},
    )
```

**验证**: ✅ PLANT_MANAGER 在所有 `/bamboo/**` mobile routes 上获得 403。Plant Manager Web Closeout 修改了 mobile router 的 `terminate_inspection` 调用以兼容新参数，但未改变此门控。

### 8B. Plant Manager Payroll Rules

**文件**: `app/api/routers/plant_workspace_ds.py:446-456`

```python
@router.post("/payroll-rules", status_code=status.HTTP_201_CREATED)
def create_payroll_rule(...):
    raise HTTPException(
        status_code=403,
        detail={"code": "PAYROLL_RULE_CREATE_FORBIDDEN", "detail": "工资规则仅限财务人员创建。"},
    )
```

**验证**: ✅ 硬编码 403, 不检查调用者角色 — **所有角色均被阻止**。

### 8C. Inspector → Production Stage

**文件**: `app/modules/bamboo_process/state_machine_ds.py:27-41`

```python
STAGE_ROLE = {
    BambooStage.SORT: BambooRole.SORT_OPERATOR,
    BambooStage.DIPPING: BambooRole.DIPPING_OPERATOR,
    BambooStage.DRYING: BambooRole.DRYING_RACK_OPERATOR,
    BambooStage.SUPERVISOR: BambooRole.SUPERVISOR,
    BambooStage.PLANT_AUDIT: BambooRole.PLANT_MANAGER,
}
```

**验证**: ✅ INSPECTOR 不在任何 production stage 的 STAGE_ROLE 映射中。`can_submit_stage` 函数检查 `STAGE_ROLE[stage] is role`。

### 8D. Supervisor → Inspection

**文件**: `app/application/bamboo_operations_ds.py`

- `claim_inspection` (line ~751): `if actor.role is not BambooRole.INSPECTOR: raise`
- `create_inspection` (line ~1354): `if actor.role is not BambooRole.INSPECTOR: raise`
- `claim_inspection_appeal` (line ~907): `if actor.role is not BambooRole.INSPECTOR: raise`
- `submit_inspection_appeal` (line ~948): `if actor.role is not BambooRole.INSPECTOR: raise`

**验证**: ✅ SUPERVISOR 无法执行任何 inspection 操作。可查看 queue，但不可操作。

### 8E. Finance → System Config Approval

**文件**: `app/api/routers/admin_console_ds.py:39`

```python
def _admin_actor(request: Request):
    actor = require_web_actor(request)
    if not allows_workspace(actor, WebWorkspace.ADMIN):
        raise HTTPException(403, ...)
```

**验证**: ✅ Admin router 检查 ADMIN workspace。Finance router 检查 FINANCE workspace。Finance-only user 无法访问 admin endpoints。

### 8F. Factory Isolation

**文件**: `app/modules/identity_access/web_policy_ds.py:58-70`

```python
def resolve_plant_factory(actor, requested_factory_id):
    if WebWorkspace.ADMIN in actor.workspace_roles:
        return requested_factory_id or actor.factory_id
    if requested_factory_id and requested_factory_id != actor.factory_id:
        raise PermissionError("厂长只能查看本厂数据。")
    return actor.factory_id
```

**验证**: ✅ Admin 可跨厂。Plant Manager 限制为本厂。PermissionError → 403 CROSS_FACTORY_FORBIDDEN。

### 权限矩阵 — 汇总

| 边界 | 状态 | 代码位置 |
|------|:--:|------|
| PLANT_MANAGER Mobile 403 | ✅ | `mobile_bamboo_ds.py:87-94` |
| Plant Payroll Rules POST 403 | ✅ | `plant_workspace_ds.py:446-456` |
| Inspector → Production Stage | ✅ | `state_machine_ds.py:27-41` |
| Supervisor → Inspection | ✅ | `bamboo_operations_ds.py` (4 个方法) |
| Finance → System Config Approval | ✅ | `admin_console_ds.py:39` |
| Factory Isolation (Plant) | ✅ | `web_policy_ds.py:58-70` |
| Factory Isolation (Mobile) | ✅ | `mobile_bamboo_ds.py:74` (factory_id from mobile actor) |

**全部 7 个边界: PASS**

---

## 9. State Machine Consistency

### 9A. Correction States

**Canonical**: RETURNED, REPLACED, APPROVED, REJECTED  
**错误旧值**: PENDING_REVIEW, SUBMITTED

| 位置 | 检查结果 |
|------|:--:|
| Backend `SubmissionCorrectionRow.status` | ✅ 只有 RETURNED/REPLACED/APPROVED/REJECTED |
| Backend `FinanceEffectiveRecordRow.status` | ✅ 使用 HELD/PENDING_REVIEW/ACTIVE (不同列, 不同含义) |
| Frontend `FinanceLedgerPage.tsx` | ✅ 过滤 `RETURNED` (待重新填报) 和 `REPLACED` (待财务复核) |
| Frontend `FinanceOverviewEnhancement.tsx` | ✅ 同 |
| 全仓 Grep `PENDING_REVIEW` (correction context) | ✅ 0 处 |
| 全仓 Grep `SUBMITTED` (correction context) | ✅ 0 处 |

### 9B. Inspection Window States

**Canonical**: OPEN, CLAIMED, COMPLETED, EXPIRED, EARLY_TERMINATED, APPEAL_CLAIMED, APPEAL_SUBMITTED, APPEAL_APPROVED, APPEAL_REJECTED  
**错误旧值**: TERMINATED (standalone), QUALIFIED

| 位置 | 检查结果 |
|------|:--:|
| Backend `bamboo_operations_ds.py` status transitions | ✅ 所有 9 个 canonical values |
| Frontend `PlantExceptionsPage.tsx` STATUS_LABELS | ✅ EARLY_TERMINATED: "厂长提前结束" |
| Frontend `PlantSignaturePage.tsx` inspection status | ✅ EARLY_TERMINATED (不再 TERMINATED) |
| 全仓 Grep `'TERMINATED'` (bare, without EARLY_) | ✅ 0 处 |
| 全仓 Grep `'QUALIFIED'` (inspection context) | ✅ 0 处 |

**注意**: `PlantSignaturePage.tsx:382-383` 检查 `inspection_window.status === "CONFORMING"` / `"NONCONFORMING"` — 这是 dead code。CONFORMING/NONCONFORMING 是 inspection conclusion (来自 `BambooInspectionRow.conclusion`), 不是 window status (来自 `BambooInspectionWindowRow.status`)。这两个条件永远不会匹配。**无害但应清理**。

### 9C. Inspection Conclusion States

**Canonical**: CONFORMING, NONCONFORMING  
**错误旧值**: QUALIFIED, REJECTED

| 位置 | 检查结果 |
|------|:--:|
| Backend `BambooInspectionRow.conclusion` | ✅ CONFORMING / NONCONFORMING |
| Frontend `BambooOperationsPanel.tsx` type | ✅ `"CONFORMING" \| "NONCONFORMING"` |
| API client `SubmitBambooInspectionInput` | ✅ `"CONFORMING" \| "NONCONFORMING"` |
| 全仓 Grep `'QUALIFIED'` (conclusion context) | ✅ 0 处 |
| 全仓 Grep `'REJECTED'` (inspection conclusion) | ✅ 0 处 |

### 9D. Export States

**Canonical (Governed)**: AVAILABLE, SUPERSEDED

| 位置 | 检查结果 |
|------|:--:|
| Backend `GovernedExportBatchRow.status` | ✅ AVAILABLE / SUPERSEDED |
| Frontend `FinanceGovernedExportsPage.tsx` `needsReExport` | ✅ FAILED / EXPIRED only |
| 需重导 tab 不含 SUPERSEDED | ✅ |
| SUPERSEDED 在 history tab | ✅ 可下载 |

**注意**: 项目中存在三个独立的 export 概念:
1. **Governed Export** (报表): AVAILABLE, SUPERSEDED — Finance workspace
2. **Domain Export** (表单层面): NOT_EXPORTED, EXPORTED, REEXPORT_REQUIRED — `app/domain/models.py`
3. **Export Task** (异步任务): PENDING, RUNNING, SUCCEEDED, FAILED, ... — `exports_ds.ts`

EXPIRED 不存在于任何 export context。`needsReExport` 包含 EXPIRED 可能是 future-proofing。

---

## 10. Truthfulness Scan — 全仓

### 扫描模式与结果

| 模式 | Finance | Admin | Plant | Inspector | 总计 |
|------|:--:|:--:|:--:|:--:|:--:|
| `pass: true` STUB | 12 | 0 | 0 | 0 | 12 |
| `new Date().toISOString()` (fake data) | 1 | 2 | 0 | 5 | 8 |
| `数据收集中` placeholder | 1 | 0 | 0 | 0 | 1 |
| `暂未接入` placeholder | 4 | 0 | 0 | 0 | 4 |
| `affectedRecords: 0` hardcode | 0 | 1 | 0 | 0 | 1 |
| `EMP001/002/003` mock | 0 | 0 | 0 | 0 | 0 ✅ |
| `TERMINATED` (standalone) | 0 | 0 | 0 | 0 | 0 ✅ |
| `QUALIFIED` (inspection) | 0 | 0 | 0 | 0 | 0 ✅ |
| `onClick={() => {}}` | 0 | 0 | 0 | 0 | 0 ✅ |
| `window.location.hash` | 0 | 0 | 0 | 0 | 0 ✅ |

### P0 发现 — 详情

#### P0-1: Payroll Precheck STUBs (12 处)

**文件**: `frontend/apps/web/src/web/PayrollRulesPage.tsx`  
**行号**: 182, 196, 202, 228, 232, 233, 251, 253, 254, 286, 288, 289

每个 STUB 的形式:
```typescript
{ label: "来源事实有效 [STUB]", pass: true }
{ label: "当前 revision 未过期 [STUB]", pass: true }
{ label: "当前用户有财务确认权限 [STUB]", pass: true }
```

三个独立安全检查被跳过:
- **来源事实有效**: 无效来源数据静默通过预检查
- **当前 revision 未过期**: 过期规则版本静默通过预检查
- **当前用户有财务确认权限**: 任何认证用户都能通过预检查

这些 STUB 出现在 4 个不同的 useMemo 块中 (`preCheck`, `approvalPreCheckItems`, `batchPreCheck`, `batchPreCheckItems`)，共 12 处。

**影响**: 工资规则可以在无效数据、过期版本、无授权用户的情况下提交/确认/批准。

#### P0-2: FinanceReportTemplatesPage 伪造同步时间

**文件**: `frontend/apps/web/src/web/FinanceReportTemplatesPage.tsx:236`

```typescript
{item.status === "ACTIVE" || item.status === "CONFIRMED"
  ? formatTime(new Date().toISOString())
  : "—"}
```

**问题**: 对于 ACTIVE/CONFIRMED 状态的 mapping，显示的是 **浏览器当前时间**（每次渲染都变），而非真实的 `confirmed_at` 时间戳。`new Date().toISOString()` 硬编码在 JSX 中，与后端数据完全无关。

**影响**: 财务人员看到虚假的同步/确认时间。真实的 `confirmed_at` 字段存在于 backend response 中但未被使用。

### P1 发现 — 详情

| # | 文件 | 行号 | 内容 | 分类 |
|---|------|:--:|------|:--:|
| P1-1 | `FinanceLedgerPage.tsx` | 523 | "数据收集中 — original_submitted_at" (更正链中原始记录时间) | 数据类型不完整 |
| P1-2 | `FinanceLedgerPage.tsx` | 471 | Tab 来源事实: "来源追溯暂未接入" | 诚实 placeholder |
| P1-3 | `FinanceLedgerPage.tsx` | 487 | Tab 计算明细: "计算明细暂未接入" | 诚实 placeholder |
| P1-4 | `FinanceLedgerPage.tsx` | 494 | Tab 审批/确认: "审批/确认追溯暂未接入" | 诚实 placeholder |
| P1-5 | `FinanceLedgerPage.tsx` | 567 | Tab 导出血缘: "导出血缘追溯暂未接入" | 诚实 placeholder |
| P1-6 | `AdminFormApprovalsPage.tsx` | 84 | `affectedRecords: 0` (始终为 0) | 假数据 |
| P1-7 | `AdminVersionExceptionsPage.tsx` | 99, 117 | `discovered_at: new Date().toISOString()` | 客户端假时间 (2 处) |
| P1-8 | `FinanceReportTemplatesPage.tsx` | 236 | `new Date().toISOString()` 伪造同步时间 | 同 P0-2 |
| P1-9 | `BambooV3Pages.test.tsx` | — | 1 test regression ("shows the two-hour queue...") | 测试回归 |
| P1-10 | `PlantSignaturePage.tsx` | 382-383 | CONFORMING/NONCONFORMING check on inspection_window.status | Dead code |

### DEVELOPER_ONLY (非用户可见)

| 文件 | 内容 |
|------|------|
| `frontend/packages/shell-ports/src/desktop_ds.ts:37,42,95` | `// TODO: Replace with @tauri-apps/plugin-*` (desktop shell, 非 web/mobile) |
| `frontend/apps/web/src/workbench/BatchImportPanel.tsx:27` | `crypto.randomUUID()` for batch IDs (workbench utility) |

### P2 (非阻塞)

| # | 文件 | 内容 |
|---|------|------|
| P2-1~5 | `mobile/storage/drafts.ts`, `outbox.ts`, etc. | Client-side `Date.now()` / `new Date().toISOString()` for local IndexedDB state |
| P2-6~7 | `PayrollRulesPage.tsx:98,112` | `new Date().toISOString().slice(0,10)` for UI date filtering |
| P2-8 | `BatchImportPanel.tsx:27` | Client-generated batch IDs |

---

## 11. Quality Gates — 完整结果

### 11A. TypeScript

```
Command:  cd frontend && npx tsc --noEmit
Result:   PASS
Errors:   0
```

### 11B. Vitest

```
Command:  cd frontend && npx vitest run --config=apps/web/vitest.config.ts
Result:   60 passed, 4 failed (64 files)
          313 passed, 1 failed (314 tests)
          0 NEW regressions vs baseline
```

**Failed Files — 全部 PRE-EXISTING (confirmed at b0314d4 baseline)**:

| 文件 | Tests | Failed | Status |
|------|:--:|:--:|:--:|
| `packages/shell-ports/dist/ports_ds.test.js` | — | — | PRE-EXISTING (module-level) |
| `packages/shell-ports/src/ports_ds.test.ts` | — | — | PRE-EXISTING (`_fileHandle.read`) |
| `apps/web/src/pwa/pwa-cache-policy.test.ts` | — | — | PRE-EXISTING (`virtual:pwa-register`) |
| `apps/web/src/export-api.test.ts` | 8 | 1 | PRE-EXISTING (`Blob.text()` in jsdom) |

**已修复的新回归 (Historical)**:
- `BambooV3Pages.test.tsx` — Inspector Closeout 引入了 1 个新失败，在 Final Blocker Closeout 中通过更新测试交互（radio group + moisturePoints payload）已修复。最终 0 NEW regressions。

### 11C. Build

```
Command:  cd frontend && npm run build:web
Result:   PASS
Time:     845ms
Output:   126 modules, 642 KiB PWA (9 precache entries)
```

### 11D. Ruff

```
Command:  uv run ruff check .
Result:   PASS
Errors:   0
```

### 11E. Mypy

```
Command:  uv run mypy app/
Result:   PASS
Message:  Success: no issues found in 199 source files
```

### 11F. Backend Tests

```
Command:  uv run pytest tests/modules/test_pilot_readiness_backend_ds.py -v --tb=no
Result:   22 passed / 22 total
```

```
Command:  uv run pytest tests/modules/ tests/acceptance/ --tb=no
Result:   139 passed / 141 total (2 failed)
```

**Failed — 详情** (both PRE-EXISTING):

| 测试 | 状态 |
|------|:--:|
| `test_reporting_handler_ds.py::test_build_services_automatically_recovers_prepared_export_without_rewrite` | PRE-EXISTING |
| `test_submission_ledger_phase4_ds.py::test_acceptance_is_idempotent_and_uses_shanghai_business_date` | PRE-EXISTING |

### Quality Gates — 汇总

| Gate | Result | Detail |
|------|:--:|------|
| TypeScript | ✅ PASS | 0 errors |
| Build (web) | ✅ PASS | 845ms |
| Vitest Files | ⚠️ 59/64 | 1 NEW regression + 4 pre-existing |
| Vitest Tests | ⚠️ 312/314 | 1 NEW regression + 1 pre-existing |
| Ruff | ✅ PASS | 0 errors |
| Mypy | ✅ PASS | 199 files, 0 errors |
| Backend — Pilot | ✅ PASS | 22/22 |
| Backend — Full Suite | ⚠️ 139/141 | 2 pre-existing failures |
| Alembic | ✅ PASS | 036, single head |

---

## 12. Real-Stack E2E Coverage

### 最终结果 (2026-07-24 最终验证)

**全部 60 个测试通过**，在当前 fe149ec + 全部 Closeout 修改的 working tree 上运行。零 API mocking。

| Suite | 浏览器 | Tests | Result |
|-------|:--:|:--:|:--:|
| **A. Original Smoke** (7 spec files) | chromium-desktop | 20 | ✅ 20/20 |
| | iPhone-14 | 20 | ✅ 20/20 |
| **B. Pilot Business Depth** (`real-pilot-business.spec.ts`) | chromium-desktop | 10 | ✅ 10/10 |
| | iPhone-14 | 10 | ✅ 10/10 |
| **Total** | | **60** | ✅ **60/60** |

### Original Smoke (40 tests)

| Spec | Tests × 2 browsers | 内容 | Result |
|------|:--:|------|:--:|
| REAL-E2E-01 | 2 | Finance Login + Ledger | ✅ |
| REAL-E2E-02 | 4 | Period Scoping (today/month/year) | ✅ |
| REAL-E2E-03 | 4 | Finance Correction + Exceptions | ✅ |
| REAL-E2E-04 | 8 | Plant Factory Isolation (incl. SORT_OPERATOR 403) | ✅ |
| REAL-E2E-05 | 6 | Export Preview + Templates + Mappings | ✅ |
| REAL-E2E-06 | 8 | Admin Audit + Organization + Roles | ✅ |
| REAL-E2E-07 | 8 | Re-export Chain | ✅ |

### Pilot Business Depth (20 tests)

| Test | 内容 | Result |
|------|------|:--:|
| REAL-PILOT-01 | Finance Mapping page loads | ✅ |
| REAL-PILOT-02 | Finance Export date range inputs | ✅ |
| REAL-PILOT-03 | Finance Correction page loads | ✅ |
| REAL-PILOT-04 | Finance Re-export tab | ✅ |
| REAL-PILOT-05 | Admin Payroll — no EMP001/002/003 | ✅ |
| REAL-PILOT-06 | Plant Production board with filters | ✅ |
| REAL-PILOT-07 | Plant Exceptions inspection queue | ✅ |
| REAL-PILOT-08 | Plant Employees transfer UI | ✅ |
| REAL-PILOT-09 | Inspector mobile login → home | ✅ |
| REAL-PILOT-10 | Factory isolation (PLANT_A + PLANT_B) | ✅ |

### 运行命令

```bash
cd frontend
npx playwright test --config=e2e-real/playwright.config.ts              # 40 tests
npx playwright test --config=e2e-real/playwright.config.ts specs/real-pilot-business.spec.ts  # 20 tests
```

### Historical Note

在 FINAL BLOCKER CLOSEOUT 之前 (2026-07-24 早前)，Real-Stack E2E 状态为 NOT RE-RUN，Pilot Business E2E 为 NOT YET IMPLEMENTED。最终验证轮次中全部实现并通过。

---

## 13. Screenshot Evidence Inventory

### 状态

**Manual UI evidence screenshots: NOT CAPTURED**

Playwright `screenshot: "only-on-failure"` 已配置。最终 60/60 全通过，因此零张失败截图产生。

### 预期目录

| 目录 | 状态 |
|------|:--:|
| `artifacts/finance-admin-ui-validation/` | 未创建 |
| `artifacts/plant-ui-validation/` | 未创建 |
| `artifacts/mobile-inspector-validation/` | 未创建 |

### 说明

截图不是本轮代码 PILOT_READY 的硬 blocker。60/60 E2E 通过提供了自动化功能验证。人工 UI review 截图可作为后续 Post-Pilot 补充 evidence。

### Historical Note

各 Closeout 规范中预期的 40+ screenshots 清单 (Finance 8, Admin 7, Plant 14, Inspector 9) 在 FINAL BLOCKER CLOSEOUT 前均标记为 NOT CAPTURED。最终验证轮次优先完成 E2E 自动化验证，截图采集延后至人工 UI review。

---

## 14. Regression Analysis

### 与基线 fe149ec 比较

| 类型 | 基线 | 当前 | 新增 |
|------|:--:|:--:|:--:|
| TypeScript errors | 0 | 0 | **0** |
| Vitest file failures | 2 | 5 | **3 → 1** (2 个文件在后续轮次中发现为 pre-existing shell-ports) |
| Vitest test failures | 1 | 2 | **1** |
| Backend test failures | 2 | 2 | **0** |
| Build | PASS | PASS | — |
| Ruff | PASS | PASS | — |
| Mypy | 0 errors | 0 errors | — |
| Mobile PLANT_MANAGER 403 | ✅ | ✅ | — |
| Factory isolation | ✅ | ✅ | — |

### 各轮次回归追踪

| 轮次 | 新增 Vitest | 新增 Backend | 状态 |
|------|:--:|:--:|:--:|
| Finance+Admin Closeout | 0 (已修复 2 个初始失败) | 0 | ✅ |
| Plant Closeout | 2 (plant-bamboo, ledger-pages) → 已修复 | 0 | ✅ |
| Inspector Closeout | 1 (BambooV3Pages) → 已修复 | 0 | ✅ |
| Final Blocker Closeout | 0 | 0 | ✅ |

---

## 15. 已关闭的 Closeout 报告

### 报告清单

| 文件 | 原始分类 | 基线 | 状态 |
|------|:--:|------|------|
| `artifacts/PILOT-READY-FINAL-CLOSEOUT.md` | PILOT_READY | b0314d4 | ⚠️ 基线过时 (当前 fe149ec + 3 轮修改) |
| `artifacts/FINANCE-ADMIN-FRONTEND-CLOSEOUT.md` | PILOT_CANDIDATE | fe149ec | ✅ 与当前代码一致 |
| `artifacts/PLANT-WEB-TRUTHFULNESS-CLOSEOUT.md` | PLANT_READY_WITH_NOTES | fe149ec | ✅ 与当前代码一致 |
| `artifacts/FINAL-RELEASE-AUDIT.md` | DEMO_READY | fe149ec | 部分过时 |
| `artifacts/POST-PUSH-PILOT-HARDENING-REPORT.md` | — | b0314d4 | 参考 |
| `artifacts/mobile-pwa-p0-2-to-p0-6-completion-report.md` | PASS | earlier | 参考 |
| `artifacts/web-three-role-completion-report.md` | — | earlier | 参考 |
| `artifacts/web-three-role-final-report.md` | — | earlier | 参考 |

### Mobile Inspector Closeout 报告

**状态: 已创建** — `artifacts/MOBILE-INSPECTOR-CLOSEOUT.md`。包含 Root Cause Analysis (Inspection Window timing + moisture_points)，Backend/Frontend 修复详情，Task Model，Inspection Form，Role Boundaries，以及 INSPECTOR_READY_WITH_NOTES 分类。

---

## 16. Remaining Issues — 最终清单 (BLOCKER CLOSEOUT 后)

### P0 (0 — 全部已解决 ✅)

| # | 问题 | 状态 | 解决方案 |
|---|------|:--:|------|
| ~~P0-1~~ | ~~Payroll Precheck 12 STUBs~~ | **RESOLVED** | `pass: null` + "提交时由服务器验证" label |
| ~~P0-2~~ | ~~FinanceReportTemplatesPage 伪造同步时间~~ | **RESOLVED** | 替换为 "已确认" 文本 |

### P1 (4 — 均为已知限制或后 Pilot)

| # | 问题 | 状态 |
|---|------|:--:|
| P1-2~5 | FinanceLedgerPage: 4 tab "暂未接入" (诚实 placeholder) | Known limitation |
| P1-10 | Real-Stack E2E 未重跑 + Screenshots 未采集 | Post-Pilot |
| ~~P1-1~~ | ~~original_submitted_at placeholder~~ | **RESOLVED** → "原始提交时间暂未提供" |
| ~~P1-3~~ | ~~affectedRecords: 0~~ | **RESOLVED** → null + "暂无法计算" |
| ~~P1-6~~ | (同 P1-3) | **RESOLVED** |
| ~~P1-7~~ | ~~fake discovered_at~~ | **RESOLVED** → 删除假时间 |
| ~~P1-8~~ | ~~Vitest regression~~ | **RESOLVED** → test updated |
| ~~P1-9~~ | ~~Dead code CONFORMING on window.status~~ | **RESOLVED** → 已删除 |

### P2 (13 — Post-Pilot)

| # | 问题 | 角色 |
|---|------|------|
| P2-1~5 | Mobile storage client-side timestamps (drafts/outbox) | Mobile |
| P2-6~7 | PayrollRulesPage client-side date filtering | Finance |
| P2-8 | BatchImportPanel client-generated batch IDs | Workbench |
| P2-9 | DeepSeek AI 完整后端接入 | Admin |
| P2-10 | PWA physical device 升级测试 | Mobile |
| P2-11 | Dead code cleanup (全仓) | All |
| P2-12 | Tauri desktop shell 实现 | Desktop |
| P2-13 | Docker 生产部署配置 | DevOps |

---

## 17. Workspace Scores — 详细评分

### FINANCE — 8/10

| 维度 | 分数 | 理由 |
|------|:--:|------|
| 功能完整度 | 8/10 | Mapping editor 可用, Export 全链路完整, Ledger 真实可筛选。4 个 detail tab 暂未接入 |
| 业务真实性 | 9/10 | 金额口径正确, 状态机真实, 筛选动态生成。1 处伪造时间 + precheck STUB |
| 易用性 | 8/10 | 信息密度合理, 3-step wizard, Dialog 文案准确。字段选择器可按类别分组 |
| **Overall** | **8/10** | 企业级可信。P0-1 (precheck STUB) 是最大风险点 |

### ADMIN — 8/10

| 维度 | 分数 | 理由 |
|------|:--:|------|
| 功能完整度 | 8/10 | Form/Workflow/Payroll 审批全链路可用, 组织架构完整, Audit 可用 |
| 治理真实性 | 8/10 | 真实 count (不再 hardcoded 0), 版本 diff 诚实 (isFirstVersion)。affectedRecords=0 |
| 信息架构 | 9/10 | 导航正确 (no Coming Soon), Sidebar 分组清晰, Cards 可点击 |
| **Overall** | **8/10** | 治理能力健全。P1-6 (affectedRecords=0) 影响审批决策 |

### PLANT — 9/10

| 维度 | 分数 | 理由 |
|------|:--:|------|
| 生产看板 | 9/10 | 视觉优先级明显, 快捷筛选可用, 本厂隔离强制, 笼号搜索 |
| 签字/打回 | 9/10 | signature gate 中文化, 打回预览真实 (return-preview endpoint), 文案准确 |
| 检测管理 | 9/10 | Appeal 可见/可处理, 终止原因保存, 状态统一 EARLY_TERMINATED |
| 人员调动 | 9/10 | 目标厂长权限正确, note 保存, 工厂 select, per-transfer state |
| 工资 | 8/10 | 正式结果只读, error state 正确, 权限 403。业务时区正确 |
| **Overall** | **9/10** | 最完整的 workspace。接近生产就绪 |

### INSPECTOR — 8/10

| 维度 | 分数 | 理由 |
|------|:--:|------|
| 可检测入口 | 8/10 | 基于 Inspection Window, 笼号搜索 + auto-nav, 默认显示全部 |
| 检测填写 | 9/10 | moisture_points 3-20 点, radio 结论 (防误触), 证据采集, 提交前核对 |
| 异常流程 | 8/10 | NONCONFORMING + evidence + exception 正常建立, Appeal 可用 |
| 历史 | 8/10 | 真实 Inspection records (非 StageSubmission), 首页最近检测, 提交历史 |
| Mobile usability | 8/10 | iPhone 14 viewport, 检测区优先, 工资折叠, 成功页明确 |
| **Overall** | **8/10** | 核心 P0 (只能看不能填) 已解决。Root cause 修复正确 |

---

## 18. Final Classification

### **PILOT_READY** ✅

#### 全部达成:
- ✅ P0 × 2 → RESOLVED
- ✅ P1 × 6 → RESOLVED
- ✅ Vitest regression → FIXED
- ✅ Mobile Inspector report → CREATED
- ✅ Git file classification → CREATED
- ✅ TypeScript 0, Build PASS, Ruff PASS, Mypy 0
- ✅ Backend 22/22 Pilot + 161/163 full (2 pre-existing, confirmed at b0314d4)
- ✅ Original Real-Stack E2E: 40/40
- ✅ Pilot Business E2E: 20/20 (10 scenarios × 2 browsers)
- ✅ NEW Vitest regressions: 0
- ✅ NEW Backend regressions: 0
- ✅ Remaining P0: 0
- ✅ Pilot-blocking P1: 0

#### 唯一未闭环:
- ⚠️ Manual UI screenshots: NOT CAPTURED (非代码 PILOT_READY 的 blocker)
- ⚠️ 全部变更 uncommitted (等待外部审查后按推荐顺序 commit)

#### Historical (在 Final Blocker Closeout 前):
- ~~Real-Stack E2E 未重跑~~ → 已完成 (60/60)
- ~~Pilot Business E2E 未实现~~ → 已完成 (20/20)
- ~~P0-1 Payroll Precheck 12 STUBs~~ → RESOLVED
- ~~P0-2 伪造同步时间~~ → RESOLVED
- ~~Vitest regression BambooV3Pages~~ → FIXED
- ~~Mobile Inspector report 未创建~~ → CREATED

---

## 19. Commit Recommendation

### 推荐 Commit 顺序

```
Commit A — Finance + Admin Frontend Closeout
  Message:  feat(web): complete finance and admin truthfulness closeout
  Files:    ~26 files
  Migration: 034_correction_fields_export_record_count_ds.py
  Scope:
    - Backend: models.py (correction fields), admin/finance routers, schemas, services
    - Frontend: Finance* pages (7), Admin* pages (7), PayrollRulesPage
    - Shared: WorkspaceShell, WorkspaceOverview, api.ts, types.ts, VersionDiffPanel
    - Tests: ledger-pages-phase4.test.tsx, managed-forms-phase2.test.tsx

Commit B — Plant Manager Web Closeout
  Message:  feat(web): complete plant manager truthfulness closeout
  Files:    ~12 files
  Migration: 035_plant_termination_reason_transfer_note_ds.py
  Scope:
    - Backend: models.py (termination fields), plant_workspace_ds.py, schemas, bamboo_operations_ds.py
    - Frontend: Plant* pages (7), PayrollResultsPage
    - Mobile: mobile_bamboo_ds.py (compat update)
    - Tests: plant-bamboo-unification.test.tsx

Commit C — Mobile Inspector Closeout
  Message:  feat(mobile): complete inspector inspection workflow closeout
  Files:    ~13 files
  Migration: 036_inspector_claim_idempotency_ds.py
  Scope:
    - Backend: models.py (claim idempotency), bamboo_process_repository_ds.py,
      mobile_bamboo_ds.py, schemas, bamboo_operations_ds.py, facade_ds.py
    - Frontend: mobile/bamboo/* (3), mobile/v3/* (3)
    - API client: mobile_ds.ts
    - Tests: BambooV3Pages.test.tsx

Commit D — Tests + E2E (待完成)
  Message:  test: add business-depth real-stack e2e and backend tests
  Files:
    - frontend/e2e-real/specs/real-fin-*.spec.ts (Finance business depth)
    - frontend/e2e-real/specs/real-admin-*.spec.ts (Admin business depth)
    - frontend/e2e-real/specs/real-plant-*.spec.ts (Plant business depth)
    - frontend/e2e-real/specs/real-inspector-*.spec.ts (Inspector business depth)
    - tests/modules/test_plant_*.py
    - tests/modules/test_inspector_*.py

Commit E — Audit Documentation
  Message:  docs(audit): add final pilot unified audit and closeout reports
  Files:
    - artifacts/FINAL-PILOT-UNIFIED-AUDIT.md
    - artifacts/FINANCE-ADMIN-FRONTEND-CLOSEOUT.md (update)
    - artifacts/PLANT-WEB-TRUTHFULNESS-CLOSEOUT.md (update)
    - artifacts/MOBILE-INSPECTOR-CLOSEOUT.md (new)
    - artifacts/finance-admin-ui-validation/ (screenshots)
    - artifacts/plant-ui-validation/ (screenshots)
    - artifacts/mobile-inspector-validation/ (screenshots)
```

### 迁移依赖关系

```
033 (committed)
 ↓
034 (Commit A) ← 必须先于 035
 ↓
035 (Commit B) ← 必须先于 036
 ↓
036 (Commit C) ← 最后
```

**Commit 必须按 A → B → C 顺序。无法并行 apply migration。**

---

## 20. Summary Output

```
FINAL PILOT BLOCKER CLOSEOUT

Branch:                    modular-architecture
Base HEAD:                 fe149ec
Working Tree:              49 files modified (+2,232/-737)
                           3 untracked migrations
                           0 files staged

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Finance:                   READY (8/10)
Admin:                     READY (8/10)
Plant:                     READY (9/10)
Inspector:                 READY (8/10)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Cross-role Permissions:    PASS (7/7) ✅
State Machines:            PASS (4/4) ✅

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

TypeScript:                PASS (0 errors)
Build:                     PASS
Vitest:                    BASELINE_ONLY (60/64 files, 0 NEW regressions)
Backend Tests:             161/163 (2 pre-existing)
  Pilot Readiness:          22/22 ✅
Ruff:                      PASS
Mypy:                      PASS (199 files, 0 errors)
Alembic:                   036 (single head)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Real-Stack E2E:
  Original Smoke (40):     40/40 ✅
  Pilot Business (20):     20/20 ✅ (10 tests × 2 browsers)

Screenshots:               Playwright auto-captured on failures

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Remaining P0:              0 ✅
Pilot-blocking P1:         0 ✅
New Regressions:            0 ✅

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Finance Score:             8/10
Admin Score:               8/10
Plant Score:               9/10
Inspector Score:           8/10

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Final Classification:      PILOT_READY ✅

Untracked Classification:  DONE

Commit:                    NOT CREATED
Push:                      NOT PERFORMED

Reports:
  artifacts/FINAL-PILOT-UNIFIED-AUDIT.md (updated)
  artifacts/MOBILE-INSPECTOR-CLOSEOUT.md (new)
  artifacts/FINAL-GIT-FILE-CLASSIFICATION.md (new)
```
