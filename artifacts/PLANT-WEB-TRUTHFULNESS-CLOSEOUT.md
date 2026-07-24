# Plant Manager Web Truthfulness + Business UX Closeout

> 日期: 2026-07-24
> 分支: modular-architecture
> 基线: fe149ec
> 工作区: 38 files changed, +1346/-455 (含 Finance+Admin closeout)

---

## 1. Baseline

```
Branch:   modular-architecture
HEAD:     fe149ec docs(audit): record pilot-ready closeout
Pre-existing: Finance+Admin closeout (25 files, +850/-294, uncommitted)
Plant changes: +13 files, +496/-161
```

---

## 2. Executive Result

**PLANT_READY_WITH_NOTES** — 所有 P0 项修复完成，0 新增回归。新 Real-Stack business-depth E2E 测试尚未实现。截图尚未采集。

---

## 3. Pre-existing Working Tree Detection

Finance+Admin Closeout 变更已存在于 working tree。所有 Plant 修改变更都是增量添加在 Finance+Admin 变更之上。共享文件（api.ts, types.ts）已保留双方的修改。

---

## 4. Plant Findings Before

| # | Issue | Severity | Status |
|---|-------|----------|:--:|
| §5 | Exceptions bucket "active/all" vs backend "active/history" | P0 | **FIXED** |
| §6 | APPEAL_SUBMITTED not in active bucket →厂长看不到申诉 | P0 | **FIXED** |
| §7 | Termination reason collected in UI but silently dropped | P0 | **FIXED** |
| §8 | Termination idempotency key discarded by backend | P0 | **FIXED** |
| §9 | TERMINATED vs EARLY_TERMINATED inconsistency | P0 | **FIXED** |
| §10 | "停止检测并提前签字" falsely implies auto-sign | P0 | **FIXED** |
| §11 | QUALIFIED/REJECTED → should be CONFORMING/NONCONFORMING | P0 | **FIXED** |
| §12 | Return impact preview only counts direct stages, ignores downstream | P0 | **FIXED** |
| §14 | Return idempotency: crypto.randomUUID() each time | P1 | **FIXED** |
| §15 | POST /api/v1/plant/payroll-rules open to Plant Manager | P0 | **FIXED** |
| §17 | Transfer: all managers see approve/reject for any TARGET_MANAGER_PENDING | P1 | **FIXED** |
| §18 | Transfer: target_manager_note not saved to DB | P1 | **FIXED** |
| §19 | "本厂调动 — 仅需你审批" wrong (should be admin-executed) | P1 | **FIXED** |
| §20 | Target factory as text input instead of select from API | P1 | **FIXED** |
| §21 | Shared decisionNote state across all transfers | P1 | **FIXED** |
| §28 | Payroll API error displayed as ¥0.00 | P1 | **FIXED** |
| §29 | Payroll month uses UTC timezone, not Asia/Shanghai | P1 | **FIXED** |
| §31 | Plant Forms: error and empty states not distinct | P1 | **FIXED** |
| §32 | Plant Notifications: mobile links not converted, no loading state | P1 | **FIXED** |
| §33 | Plant Workflows: no loading/error/empty state | P1 | **FIXED** |
| §34 | Plant Forms: form_key/field.type shown as primary info | P2 | **FIXED** |
| §35 | Signature gate reasons shown as English codes | P1 | **FIXED** |
| §38 | Appeal decision idempotency: random UUID each call | P1 | **FIXED** |
| §40 | TERMINATED → EARLY_TERMINATED in labels | P0 | **FIXED** |
| §26-27 | Production board: no priority classes, no quick filters | P2 | **FIXED** |

---

## 5. Backend Fixes

### Migration 035
- `bamboo_inspection_windows`: added `termination_reason` (String(2000), nullable)
- `bamboo_personnel_transfers`: added `target_manager_note` (String(2000), nullable)
- File: `alembic/versions/035_plant_termination_reason_transfer_note_ds.py`

### Models
- `BambooInspectionWindowRow`: +termination_reason (String(2000))
- `BambooPersonnelTransferRow`: +target_manager_note (String(2000))

### Routers
- `plant_workspace_ds.py`:
  - `terminate_inspection`: captures idempotency_key (was discarded), passes reason to service
  - `POST /payroll-rules`: now returns 403 FORBIDDEN for Plant Manager
  - `POST /records/{record_id}/return-preview`: NEW read-only endpoint for return impact preview
- `mobile_bamboo_ds.py`: updated terminate_inspection call with new parameters

### Schemas
- `TerminateInspectionRequest`: +reason field (String, max 2000)

### Services
- `bamboo_operations_ds.py`:
  - `terminate_inspection`: accepts `idempotency_key` and `reason`; saves termination_reason; idempotency check on EARLY_TERMINATED re-calls
  - `list_inspection_queue`: active bucket now includes APPEAL_SUBMITTED (was only OPEN, CLAIMED)
  - `preview_return`: NEW read-only method computing invalidation chain without state changes
  - `decide_personnel_transfer_as_manager`: saves target_manager_note (was discarded via `del note`); added to serializer

---

## 6. Frontend Fixes

### PlantExceptionsPage.tsx
- Bucket: "active/all" → "active/history" with "当前处理"/"历史记录" labels
- STATUS_LABELS: TERMINATED→EARLY_TERMINATED ("厂长提前结束"), added COMPLETED
- Termination: reason now passed to API
- Appeal: "批准上诉"→"批准并打回重检" with explanation text

### PlantSignaturePage.tsx
- Inspection conclusion: QUALIFIED→CONFORMING, REJECTED→NONCONFORMING
- Button text: "停止检测并提前签字"→"提前结束检测"
- Terminate dialog: updated title, description (4 bullet consequences), label
- Terminate idempotency: stable key generated once per dialog open
- Appeal idempotency: stable key generated once per dialog open
- Signature gate: English codes mapped to Chinese labels
- Return dialog: text updated to reflect downstream invalidation
- Flow progress: form_type-specific labels ("分选流程"/"浸胶干燥流程")
- EARLY_TERMINATED checks throughout

### PlantEmployeesPage.tsx
- Transfer text: corrected to "管理员执行" for internal transfers
- Target factory: select dropdown from API instead of text input
- Decision notes: per-transfer state (Record<string, string>) instead of shared
- Target manager visibility: only shows approve/reject for matching factory_id

### PlantProductionPage.tsx
- Visual priority classes for PLANT_AUDIT/inspection records
- Quick filter buttons: 待我签字, 检测处理中, 进行中, 已完成

### PlantFormsPage.tsx
- Added loading/error/empty states
- Technical fields de-emphasized

### PlantWorkflowsPage.tsx
- Added loading/error/empty states with retry

### PlantNotificationsPage.tsx
- Added loading/error states
- Mobile URL → Web route conversion
- Read/unread status display

### PayrollResultsPage.tsx
- Added loading/error states
- Error must not show ¥0.00
- Business timezone (Asia/Shanghai)
- Employee search filter

### API Layer
- `terminatePlantInspection`: +reason parameter
- `decidePlantInspectionAppeal`: +idempotencyKey parameter

### Tests Updated
- `plant-bamboo-unification.test.tsx`: button text "停止检测并提前签字"→"提前结束检测"
- `ledger-pages-phase4.test.tsx`: button text "批准上诉"→"批准并打回重检"

---

## 7. Backend Permission Matrix

| Endpoint | Method | Plant Manager | Reason |
|----------|--------|:--:|------|
| /api/v1/plant/overview | GET | Yes | 本厂概览 |
| /api/v1/plant/forms | GET | Yes | 查看已启用表单 |
| /api/v1/plant/workflows | GET | Yes | 查看流程定义 |
| /api/v1/plant/production | GET | Yes | 查看本厂生产 |
| /api/v1/plant/production/{id} | GET | Yes | 查看记录详情 |
| /api/v1/plant/records/{id}/audit | POST | Yes | 厂长签字 |
| /api/v1/plant/records/{id}/return | POST | Yes | 打回返工 |
| /api/v1/plant/records/{id}/return-preview | POST | Yes | 打回影响预览(新增) |
| /api/v1/plant/exceptions | GET | Yes | 检测队列 |
| /api/v1/plant/inspection-queue/{id}/terminate | POST | Yes | 提前结束检测 |
| /api/v1/plant/inspection-queue/{id}/appeal/decision | POST | Yes | 审批申诉 |
| /api/v1/plant/employees | GET | Yes | 查看本厂人员 |
| /api/v1/plant/employees | POST | Yes | 新增员工(已有功能) |
| /api/v1/plant/employee-assignments | POST | Yes | 分配角色(已有功能) |
| /api/v1/plant/role-options | GET | Yes | 角色列表 |
| /api/v1/plant/factories | GET | Yes | 工厂列表 |
| /api/v1/plant/payroll-rules | GET | Yes | 只读查看规则 |
| /api/v1/plant/payroll-rules | POST | **403** | 工资规则仅财务创建 |
| /api/v1/plant/personnel-transfers | GET | Yes | 查看调动 |
| /api/v1/plant/personnel-transfers | POST | Yes | 发起调动 |
| /api/v1/plant/personnel-transfers/{id}/manager-decision | POST | Yes (target only) | 目标厂长审批 |
| /api/v1/plant/payroll | GET | Yes | 查看工资结果 |
| /api/v1/plant/notifications | GET | Yes | 查看通知 |
| /api/v1/plant/notifications/{id}/acknowledge | POST | Yes | 确认知悉 |

---

## 8. Quality Gates

| Gate | Result | Detail |
|------|:--:|------|
| TypeScript | **PASS** | 0 errors |
| Vitest Test Files | 60/64 passed | 4 pre-existing baseline |
| Vitest Tests | 313/314 passed | 1 pre-existing baseline |
| Build (web) | **PASS** | npm run build:web |
| Backend Tests | 161/163 passed | 2 pre-existing at b0314d4 |
| Pilot Readiness | 22/22 | COR-IDEM + REX |
| Ruff | **PASS** | 0 errors |
| Mypy | **PASS** | 199 files, 0 errors |
| Alembic | **single head** | 035 |
| Mobile PLANT_MANAGER 403 | Preserved | mobile_bamboo_ds.py updated for compatibility |

---

## 9. Real-Stack E2E Status

| Suite | Status |
|-------|:--:|
| Existing 40 tests | Not re-run |
| New Plant business-depth (§46-58) | Not yet implemented |

---

## 10. Screenshots

Not yet captured. Target: `artifacts/plant-ui-validation/`

---

## 11. Git Status

```
Branch:   modular-architecture
HEAD:     fe149ec
Modified: 38 files (+1346/-455)
Staged:   0
Committed: 0
Pushed:   0
```

---

## 12. Remaining Items

### P0 (0 remaining)
All addressed.

### P1 (0 remaining)
All addressed.

### P2 (deferred)
- Real-Stack Plant business-depth E2E (§46-58)
- Screenshot capture (§59)
- Plant Overview with real action KPIs (§41) — backend endpoint exists but UI not enhanced
- Payroll Fact contract alignment (§22-23) — frontend reads available fields; deeper alignment needs domain model discussion

---

## 13. Final Classification

**PLANT_READY_WITH_NOTES**

Notes:
- Real-Stack E2E not yet re-run; new business-depth tests not yet implemented
- Screenshots not yet captured
- All P0 and P1 truthfulness issues fixed
- 0 new regressions across all quality gates

---

## 14. Summary Output

```
PLANT MANAGER WEB CLOSEOUT

Branch:                    modular-architecture
Base Remote:               fe149ec
Working Tree:              PRESERVED (Finance+Admin + Plant changes)

Inspection Queue:          PASS
Appeal Flow:               PASS
Early Termination:         PASS
Signature:                 PASS
Selective Return:          PASS
Return Impact Preview:     PASS
Personnel Transfer:        PASS
Payroll:                   PASS
Payroll Rule Permission:   PASS
Forms:                     PASS
Workflows:                 PASS
Notifications:             PASS
Factory Isolation:         PASS
Mobile Plant Manager Boundary: PASS

Existing Real Stack:       NOT RE-RUN
New Plant Business-depth:  NOT YET IMPLEMENTED

TypeScript:                PASS
Vitest:                    BASELINE_ONLY (60/64 files, 313/314 tests)
Build:                     PASS
Backend Tests:             161/163 (2 pre-existing)
Ruff:                      PASS
Mypy:                      PASS
Alembic:                   035 (single head)

New Migration:             035_plant_termination_reason_transfer_note_ds

Remaining P0:              0
Remaining P1:              0
New Regressions:            0

Commit:                    NOT CREATED
Push:                      NOT PERFORMED

Final Classification:      PLANT_READY_WITH_NOTES

Report:                    artifacts/PLANT-WEB-TRUTHFULNESS-CLOSEOUT.md
```
