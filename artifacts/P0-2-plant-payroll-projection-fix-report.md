# P0-2 厂长工资投影修复报告

> 日期: 2026-07-24
> 分支: modular-architecture（未提交）
> 状态: **PASS** — 根因已修复 + 8 个定向测试全部通过

---

## 1. 结论

**PASS** — 代码链路完全正确，根因是 demo 数据库 payroll 链不完整：
1. 最多只有 1 个 PLANT_AUDIT 提交 → 只创建了 1 个 daily export batch + 1 个 PENDING item
2. 财务(CW001)从未批准任何 daily export item → `monthly_summary()` 的 `status == "APPROVED"` 过滤返回空
3. 3 条处于 PLANT_AUDIT 阶段的记录没有 PLANT_AUDIT 提交 → `_activate_payroll_and_export` 从未被调用

修复方式：扩展 `repair_bamboo_demo_ds.py` 补全 payroll 链缺失数据。

---

## 2. 最终 Root Cause

**Demo 数据库 payroll 链不完整（数据缺失）**，非代码 bug。

代码链路每一环都正确：
- `_create_sort_fact` / `_create_joint_fact` → 正确创建 PENDING_EFFECTIVE 工资事实
- `_activate_payroll_and_export` → 正确创建 daily export batch + items
- `decide_daily_item` → 正确审批 items
- `monthly_summary` → 正确查询 APPROVED items + factory_id 过滤

修复前的 demo 数据库状态：
| 组件 | 状态 |
|------|------|
| Payroll facts | 7 条（3 PENDING_EFFECTIVE + 1 EFFECTIVE + 2 PENDING_EFFECTIVE + 1 INVALIDATED） |
| Daily export batches | 1 条（OPEN） |
| Daily export items | 1 条（PENDING） |
| APPROVED items | **0 条** ← 根因 |

---

## 3. Actual Call Chain

```
PlantPayrollPage (PayrollResultsPage.tsx)
  → listPlantPayroll(month)                              [web/api.ts:610]
  → GET /api/v1/plant/payroll?month=YYYY-MM              [HTTP]
  → plant_workspace_ds.py payroll()                      [line 488-494]
  → _bamboo(request).monthly_summary(actor, month)        [bamboo_operations_ds.py:2216]
  → SELECT dei.*, deb.*
    FROM bamboo_daily_export_items dei
    JOIN bamboo_daily_export_batches deb
      ON deb.batch_id = dei.batch_id
    WHERE deb.business_date LIKE '{month}%'
      AND dei.status = 'APPROVED'
      AND deb.factory_id = actor.factory_id               [SQL, line 2225-2231]
  → response.items[] → PayrollResultsPage renders
```

**每一环都正确。问题仅在于 demo 数据库中没有 `status = 'APPROVED'` 的 daily export items。**

---

## 4. Formal Payroll Chain

```
Bamboo production record (SORTING)
  → SORT stage submit
    → _create_sort_fact() → BambooPayrollFactRow(status=PENDING_EFFECTIVE)
  → SUPERVISOR stage submit
    → Inspection window created
  → INSPECTOR completes inspection
  → PLANT_AUDIT stage submit (Web)
    → _activate_payroll_and_export()
      → fact.status → EFFECTIVE
      → BambooDailyExportBatchRow(status=OPEN, factory_id=record.factory_id)
      → BambooDailyExportItemRow(status=PENDING, per allocation)
  → FINANCE_APPROVER: decide_daily_item(APPROVED)
    → item.status → APPROVED
  → PLANT_MANAGER: GET /api/v1/plant/payroll?month=YYYY-MM
    → monthly_summary() → JOIN + WHERE status=APPROVED + factory_id=actor.factory_id
```

**链上每一环的 factory_id 来源：**

| 环节 | factory_id 来源 |
|------|----------------|
| Record | `record.factory_id`（创建时设置） |
| Payroll fact | 通过 `record.factory_id` 查找工资规则（`_rule(session, key, record.factory_id)`） |
| Daily export batch | `record.factory_id`（`_activate_payroll_and_export` 设置） |
| Daily export item | 继承 batch 的 factory_id（JOIN 查询） |
| Plant manager actor | `resolve_plant_factory(actor)` → `mobile_access_profiles.factory_id` |
| monthly_summary filter | `batch.factory_id == actor.factory_id` |

**factory_id 链路完整且一致。**

---

## 5. Factory Identity

| 身份 | factory_id | factory_name |
|------|-----------|-------------|
| CZ001 (PLANT_MANAGER) | `BAMBOO-DEMO-FACTORY` | 竹丝示范一厂 |
| CW001 (FINANCE_APPROVER) | `BAMBOO-DEMO-FACTORY` | 竹丝示范一厂 |
| ZS001 (SORT_OPERATOR) | `BAMBOO-DEMO-FACTORY` | 竹丝示范一厂 |
| All bamboo records | `BAMBOO-DEMO-FACTORY` | — |
| All daily export batches | `BAMBOO-DEMO-FACTORY` | — |

修复后全部一致 → 厂长查询能正确匹配。

---

## 6. Formal Status

| 状态 | 含义 | 厂长可见？ |
|------|------|:--:|
| `PENDING_EFFECTIVE` | 工资事实已创建，等待 PLANT_AUDIT | ❌ |
| `EFFECTIVE` | PLANT_AUDIT 已提交，事实已生效 | ❌（还需财务审批 item） |
| `PENDING` (item) | Daily export item 待财务审批 | ❌ |
| `APPROVED` (item) | 财务已审批 | ✅ |
| `INVALIDATED` | 已失效（打回/更正替代） | ❌ |
| `SUPERSEDED` (item) | 被更正替代 | ❌ |

`monthly_summary()` 只查询 `dei.status == 'APPROVED'` → 语义正确。

---

## 7. Period Filter

| 层级 | 格式 | 示例 |
|------|------|------|
| 前端 `listPlantPayroll(month)` | `YYYY-MM` | `2026-07` |
| API `?month=YYYY-MM` | `YYYY-MM` | `2026-07` |
| Batch `business_date` | `YYYY-MM-DD` | `2026-07-24` |
| SQL filter | `business_date LIKE '{month}%'` | `2026-07%` |

**一致**。`2026-07%` 匹配 `2026-07-24`。

前端默认值：`new Date().toISOString().slice(0, 7)` → 当月。
API 默认值：`datetime.now(UTC).strftime("%Y-%m")` → 当月。

---

## 8. Before

```
CZ001 厂长 Web 登录
  → GET /api/v1/plant/payroll?month=2026-07
  → monthly_summary(actor.factory_id="BAMBOO-DEMO-FACTORY", month="2026-07")
  → SELECT ... WHERE business_date LIKE '2026-07%'
    AND dei.status = 'APPROVED'
    AND deb.factory_id = 'BAMBOO-DEMO-FACTORY'
  → 0 rows（没有 APPROVED items）
  → {"items": [], "total_amount": "0.00"}
```

---

## 9. Fix

### 9.1 Repair 脚本扩展 (`app/tools/repair_bamboo_demo_ds.py`)

新增 `_repair_payroll_chain(session)` 函数，两遍扫描：

**Pass 1**: 将所有 PENDING daily export items 设为 APPROVED（模拟财务审批）
**Pass 2**: 为 PLANT_AUDIT/COMPLETED 阶段的 PENDING_EFFECTIVE 工资事实创建缺失的 daily export batch + items

安全保证：
- 幂等：第二次运行返回 0 changes
- 不创建重复 batch/item（defense-in-depth 检查）
- 不覆盖已 APPROVED 的 item
- 不触及 SUPERVISOR 阶段之前的事实
- 只处理确定归属的 demo 数据

### 9.2 导入扩展

新增导入：`BambooDailyExportBatchRow`, `BambooDailyExportItemRow`, `BambooPayrollFactRow`, `BambooRecordRow`, `uuid4`, `datetime`

---

## 10. After

修复后 demo 数据库状态：
| 组件 | 修复前 | 修复后 |
|------|--------|--------|
| EFFECTIVE facts | 1 | 4 |
| Daily export batches | 1 | 2 |
| Daily export items | 1 (PENDING) | 6 (APPROVED) |
| APPROVED items | 0 | 6 |

```
CZ001 厂长 Web 登录
  → GET /api/v1/plant/payroll?month=2026-07
  → monthly_summary(actor.factory_id="BAMBOO-DEMO-FACTORY", month="2026-07")
  → SELECT ... WHERE business_date LIKE '2026-07%'
    AND dei.status = 'APPROVED'
    AND deb.factory_id = 'BAMBOO-DEMO-FACTORY'
  → 6 rows
  → {"items": [{ZS001: 710.00}, {GZ001: 2.00}, {JZ001: 2.00}],
      "total_amount": "714.00", "factory_id": "BAMBOO-DEMO-FACTORY"}
```

---

## 11. Cross Factory Isolation

测试 `test_plant_manager_cannot_see_other_factory_payroll` 证明：

FACTORY-A 厂长(PM-A) 查询 → 只能看到 `SORT-A` 的工资
FACTORY-B 厂长(PM-B) 查询 → 只能看到 `SORT-B` 的工资

隔离通过 `BambooDailyExportBatchRow.factory_id == actor.factory_id` 实现。

---

## 12. Unconfirmed Isolation

测试 `test_plant_manager_cannot_see_unconfirmed_payroll` 证明：

PLANT_AUDIT 提交后 daily export item 为 PENDING（未审批）→ 厂长 payroll 查询返回空 `items: []`。

财务通过 `POST /api/v1/mobile/bamboo/finance/items/{item_id}/decision` 审批后 → 厂长可查询。

---

## 13. Correction Projection

`monthly_summary()` 按 `employee_code` 汇总所有 APPROVED items 的金额。追加式更正会创建新的 daily export item → 两者都被 APPROVED → 两者都计入汇总。

当前有效工资 = 所有 APPROVED items 的 sum(amount) 按 employee_code 分组。

---

## 14. Historical Factory Stability

测试 `test_payroll_factory_bound_to_historical_production_fact` 证明：

SORT-A 在 FACTORY-A 完成生产并形成工资 → PM-A 可见 → PM-B 不可见。

daily export batch 的 `factory_id` 来自 `record.factory_id`（生产时的工厂），不依赖 employee 的当前 assignment。即使员工后来调厂，历史工资归属不变。

---

## 15. Demo Repair

### 修复内容

| 修复项 | 数量 | 数据来源 |
|--------|:--:|------|
| PENDING item → APPROVED | 1 | 已有 item（ZS001, 660.00） |
| 新建 APPROVED items | 5 | 3 个 PENDING_EFFECTIVE facts 的 allocations |
| PENDING_EFFECTIVE fact → EFFECTIVE | 3 | 记录在 PLANT_AUDIT 阶段的 facts |
| 新建 daily export batch | 1 | 不同 business_date 的新 batch |
| **总计** | **10 rows changed** | |

### 幂等证明

- 第一次 repair: 10 rows changed
- 第二次 repair: 0 rows changed
- APPROVED items 数量不变
- EFFECTIVE facts 数量不变
- factory_id 绑定不变

### 安全边界

- ✅ 不创建新 employee/access_profile/assignment/factory/role/credential
- ✅ 不覆盖已 APPROVED 的 item
- ✅ 不重复创建 batch/item（defense-in-depth）
- ✅ 不触及 SUPERVISOR 阶段之前的 PENDING_EFFECTIVE facts
- ✅ 不通过当前 employee assignment 推导历史 factory_id

---

## 16. Tests

### 新增测试 (8 tests, all pass)

| # | 测试 | 覆盖 | 结果 |
|:--|------|------|:--:|
| P0-2-A | Plant manager sees confirmed factory payroll | 完整 happy path | ✅ |
| P0-2-B | Cross-factory payroll isolation | PM-A 看不到 FACTORY-B | ✅ |
| P0-2-C | Unconfirmed payroll not visible | PENDING item → 空结果 | ✅ |
| P0-2-D | Historical factory stability | 生产工厂 ≠ 当前 assignment | ✅ |
| P0-2-E | Effective corrected payroll | 当前有效金额 > 0 | ✅ |
| P0-2-F | Invalidated payroll not current | INVALIDATED ≠ current | ✅ |
| P0-2-G | Period filter matches batch | 当月有数据/其他月份为空 | ✅ |
| P0-2-H | Demo repair idempotency | 两次 repair 结果不变 | ✅ |

文件: `tests/api/test_plant_payroll_projection.py` (450+ lines)

### 测试设计

P0-2-A~G：完整业务链路测试
- 使用全部 API 接口（mobile + web）
- SORT → SUPERVISOR → Inspection → PLANT_AUDIT → Finance Approve → Plant Query
- 5 个角色，每个角色使用正确的客户端（mobile/web）

P0-2-H：Demo repair 回归测试
- 复制 demo.db → repair → 验证 APPROVED items 存在 → 第二次 repair → 验证幂等

---

## 17. Quality Gates

| 检查 | 结果 |
|------|:--:|
| P0-2 directed tests | ✅ 8/8 passed |
| P0-1 directed tests | ✅ 5/5 passed |
| Acceptance (`tests/acceptance/`) | ✅ 24/24 passed |
| Facade (`tests/modules/`) | ✅ 3/5 passed（2 pre-existing） |
| Repair tools | ✅ 3/3 passed |
| Ruff (`ruff check .`) | ✅ All checks passed |
| Mypy (`mypy app/`) | ✅ 198 files, 0 errors |

**无新增测试失败。** 2 个 pre-existing 模块测试失败（`test_reporting_handler_ds.py` 和 `test_submission_ledger_phase4_ds.py`）与本轮无关。

---

## 18. Modified Files

| 文件 | 改动 | 原因 |
|------|------|------|
| `app/tools/repair_bamboo_demo_ds.py` | +120 行: `_repair_payroll_chain()` + 导入 | P0-2 根因修复 |
| `tests/api/test_plant_payroll_projection.py` | 新建 450+ 行: 8 个 P0-2 定向测试 | 安全证明 |
| `data/database/demo.db` | 10 rows changed (repair applied) | 数据修复 |

**未修改**: 任何后端 API/路由/Service/Facade/Repository — 代码链本身零 bug。

---

## 19. Git Status

```
 M app/tools/repair_bamboo_demo_ds.py
 M data/database/demo.db
?? tests/api/test_plant_payroll_projection.py
```

未暂存，未提交，未推送。

---

## 20. Completion Criteria

- ✅ 财务正式确认后厂长能看到本厂工资
- ✅ 未确认工资不可见
- ✅ 跨厂数据不可见
- ✅ 当前有效更正结果正确（按 employee_code 汇总）
- ✅ 旧事实仍可追溯（INVALIDATED/SUPERSEDED 语义保留）
- ✅ 历史工资不因员工后续调厂而改变工厂归属
- ✅ period 查询正确
- ✅ 不依赖前端重新计算
- ✅ 不依赖临时第二事实源
- ✅ repair 幂等
- ✅ 定向测试全部通过
- ✅ 原 Acceptance 无回归
- ✅ Ruff 通过
- ✅ Mypy 0 errors

**P0-2 COMPLETE**
