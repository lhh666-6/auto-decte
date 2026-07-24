# P0-1: 厂长 Web 生产投影修复报告

> 日期: 2026-07-24
> 分支: modular-architecture（未提交）
> 状态: **PASS** — 根因已修复 + 5 个定向测试全部通过

---

## 1. Root Cause

**厂长 (CZ001/PLANT_MANAGER) 的 `mobile_access_profiles.factory_id` 在 demo 数据库中为空字符串**，而所有竹丝生产记录的 `factory_id` 都是 `BAMBOO-DEMO-FACTORY`。

`list_production_records()` 对 PLANT_MANAGER 使用 `BambooRecordRow.factory_id == actor.factory_id` 过滤。空字符串 `""` 匹配不到任何记录 → 返回空。

同受影响的还有 ZS001, JZ001, GZ001, ZG001, JC001（全部一线工人），但他们的查询方式不同（按 employee_code 或 stage-scoped），所以症状仅表现为厂长生产列表为空。

后端代码本身**零逻辑错误** — API 链路从头到尾完全正确。

---

## 2. Actual Call Chain

```
前端: PlantProductionPage.tsx
  → getPlantProduction()                           [web/api.ts:453]
  → GET /api/v1/plant/production                   [HTTP]
  → plant_workspace_ds.py production()             [line 170]
  → _bamboo(request).list_production_records(actor) [bamboo_operations_ds.py:1600]
  → SELECT FROM bamboo_records
    WHERE factory_id = actor.factory_id             [SQL, line 1613]
    ORDER BY updated_at DESC
  → response.records[] → PlantProductionPage renders
```

**每一环都正确。问题仅在于 `actor.factory_id` 来自 demo 数据库中的 `""` 而非 `"BAMBOO-DEMO-FACTORY"`。**

---

## 3. Factory Identity

| 身份 | factory_id (修复前) | factory_id (修复后) |
|------|-------------------|-------------------|
| CZ001 (PLANT_MANAGER) | `""` | `BAMBOO-DEMO-FACTORY` |
| ZS001 (SORT_OPERATOR) | `""` | `BAMBOO-DEMO-FACTORY` |
| All bamboo records | `BAMBOO-DEMO-FACTORY` | `BAMBOO-DEMO-FACTORY` |

**修复前**: `""` ≠ `"BAMBOO-DEMO-FACTORY"` → 0 条匹配
**修复后**: `"BAMBOO-DEMO-FACTORY"` = `"BAMBOO-DEMO-FACTORY"` → 8 条匹配

---

## 4. Before

```
CZ001 厂长 Web 登录
  → GET /api/v1/plant/production
  → list_production_records(actor.factory_id="")
  → SELECT WHERE factory_id = ""
  → 0 rows → {"records": [], "overview": {"total": 0, ...}}
```

---

## 5. After

```
CZ001 厂长 Web 登录
  → GET /api/v1/plant/production
  → list_production_records(actor.factory_id="BAMBOO-DEMO-FACTORY")
  → SELECT WHERE factory_id = "BAMBOO-DEMO-FACTORY"
  → 8 rows → {"records": [...8 items...], "overview": {...}}
```

---

## 6. Stage Visibility

测试 `test_production_list_is_not_task_stage_scoped` 证明：

SORT 阶段的记录在厂长生产列表中可见。厂长"查看生产"与"当前可执行 PLANT_AUDIT"不是同一语义。

厂长生产列表展示**本厂全部阶段**的记录（SORT, DIPPING, DRYING, SUPERVISOR, PLANT_AUDIT, COMPLETED）。

---

## 7. Cross Factory Isolation

测试 `test_plant_manager_cannot_see_other_factory_records` 证明：

FACTORY-A 厂长只能看到 FACTORY-A 的记录，FACTORY-B 的记录不可见。

---

## 8. Mobile Boundary

测试 `test_plant_manager_mobile_bamboo_remains_web_only` 证明：

```
PLANT_MANAGER → GET /api/v1/mobile/bamboo/dashboard
→ 403, code: "PLANT_MANAGER_WEB_ONLY"
```

移动端拒绝未改变。

---

## 9. Tests

### 新增测试 (5 tests, all pass)

| # | 测试 | 结果 |
|:--|------|:--:|
| P0-1-A | Plant manager sees SORT-stage factory records | ✅ |
| P0-1-B | Plant manager cannot see other factory records | ✅ |
| P0-1-C | Production list is not PLANT_AUDIT-only | ✅ |
| P0-1-D | Mobile bamboo blocks PLANT_MANAGER (403) | ✅ |
| P0-1-E | Factory identity matches record factory_id | ✅ |

文件: `tests/api/test_plant_production_projection.py`

---

## 10. Quality Gates

| 检查 | 结果 |
|------|:--:|
| P0-1 directed tests | ✅ 5/5 passed |
| Acceptance (`tests/acceptance/`) | ✅ 24/24 passed |
| Facade (`tests/modules/`) | ✅ 5/5 passed |
| Repair tool tests | ✅ 3/3 passed |
| Total backend | ✅ 37/37 passed |
| Ruff (`ruff check .`) | ✅ All checks passed |
| Mypy (`mypy app/`) | ✅ 198 files, 0 errors |

---

## 11. Modified Files

| 文件 | 改动 | 原因 |
|------|------|------|
| `app/tools/repair_bamboo_demo_ds.py` | +16 行: 新增 `factory_id`/`factory_name` 修复逻辑 | P0-1/P0-2 根因修复 |
| `tests/tools/test_repair_bamboo_demo_ds.py` | +9 行: 新增 factory_id/factory_name 断言 | 回归覆盖 |
| `tests/api/test_plant_production_projection.py` | 新建 200 行: 5 个 P0-1 定向测试 | 安全证明 |
| `data/database/demo.db` | 6 名工人 factory_id 已修复 (12 行变更) | 数据修复 |

**未修改**: 任何后端 API/路由/Service/Facade/Repository — 代码链本身零 bug。

---

## 12. Git Status

```
 M app/tools/repair_bamboo_demo_ds.py
 M tests/tools/test_repair_bamboo_demo_ds.py
?? tests/api/test_plant_production_projection.py
 M data/database/demo.db
```

未暂存，未提交，未推送。
