# 厂长 Web 与 Bamboo 移动业务统一设计

## 目标

厂长只使用 Web 端。一线工人、主管、检测员继续使用移动端。厂长原有移动业务迁入 Web，但所有业务仍以既有 Bamboo 领域模型和数据库表为唯一事实源，不再维护第二套厂长通知、生产、异常、打回或工资状态。

## 权限边界

- 厂长 Web 保留：本厂概览、通知知悉、已启用表单与流程查看、生产记录查看、选择环节打回、检测申诉审批、人员调动、本厂工资查看。
- 厂长不再通过移动端进入 Bamboo 业务。
- 主管继续通过移动端选择环节打回。
- 工人、主管、检测员的既有移动端页面和交互保持冻结。
- 表单、流程和工资规则的审批及按厂启用仍只属于管理员。
- 跨厂调动继续要求来源厂长、目标厂长同时同意，最后由管理员执行。

## 单一数据源

| 领域 | 唯一事实源 |
|---|---|
| 生产记录与阶段提交 | `bamboo_records`、`bamboo_stage_submissions` |
| 生产打回 | `bamboo_returns` |
| 检测窗口、异常和申诉 | `bamboo_inspection_windows`、`bamboo_inspection_exceptions` |
| 通知与知悉 | `mobile_notifications` |
| 人员与调动 | `employee_bamboo_assignments`、`bamboo_personnel_transfers` |
| 工资事实与财务批次 | `bamboo_payroll_facts`、`bamboo_daily_export_batches`、`bamboo_daily_export_items` |
| 表单定义与按厂启用 | `managed_form_definitions`、`managed_form_versions`、`form_plant_activations` |

以下表仍可服务财务、管理员等其他场景，但厂长 Web 不再读取或写入它们：

- `finance_effective_records`
- `submission_corrections`
- `business_tasks`
- `payroll_calculation_results`
- `management_notifications`

## Web 后台边界

`/api/v1/plant/**` 继续使用 Web Cookie、CSRF 和本厂权限校验，但业务操作通过面向厂长 Web 的适配层调用既有 `BambooOperationsService`、`BambooProcessFacade` 和 Bamboo Repository。

适配层负责把 `WebActor` 转换为 `BambooActor`，不复制业务规则。生产、检测、调动、通知和工资的状态转换只能在既有 Bamboo 服务内发生。

Web 路由调整：

- `/plant/overview`：统计 Bamboo 生产记录、员工和异常。
- `/plant/notifications`：读取并更新厂长本人 `mobile_notifications`。
- `/plant/forms`：只读展示本厂启用的 Managed Form。
- `/plant/workflows`：展示实际 Bamboo 流程状态和本厂启用信息，不产生审批权。
- `/plant/production`：展示本厂 `bamboo_records`，支持详情和选择环节打回。
- `/plant/employees`：复用既有人员查询和调动流程。
- `/plant/exceptions`：展示检测异常、申诉及厂长审批动作。
- `/plant/payroll`：读取 Bamboo 工资事实及财务确认后的同源结果。

## 打回幂等与并发

主管移动端和厂长 Web 端使用同一条打回命令。命令必须包含：

- `record_id`
- `target_stages`
- `reason`
- `expected_revision`
- `idempotency_key`

`bamboo_returns` 增加幂等键、请求载荷哈希及唯一约束。处理规则：

1. 同一操作人、同一幂等键、相同载荷重复提交，返回第一次结果。
2. 同一幂等键对应不同载荷，返回 `IDEMPOTENCY_CONFLICT`。
3. `expected_revision` 与当前记录版本不符，返回 `REVISION_CONFLICT`，不产生打回记录。
4. 版本检查、阶段失效、工资事实失效、打回记录写入和记录版本递增在同一数据库事务中完成。

## Managed Form 完整提交

管理员启用的 Managed Form 必须成为移动端正式可填写表单，而不只是出现在列表中。

移动端获取列表、获取 Schema 和提交时使用同一个定义解析器。提交时校验：

- 表单对当前工厂处于启用状态；
- 当前角色与 `owner_role` 匹配；
- `definition_version_id` 与当前启用版本一致；
- 字段集合、必填字段和字段类型符合同一份 `schema_json`；
- 幂等键仍使用既有电子提交收据约束。

提交成功后继续原子写入电子表单、审计事件、事实记录和财务接收记录。

## 厂长移动端退出

后台身份认证仍共享同一套员工账号。厂长账号可以登录 Web，但移动 Bamboo 业务入口拒绝 `PLANT_MANAGER` 角色。现有 `frontend/apps/web/src/mobile/**` 不修改；权限拒绝由后台完成，避免破坏工人、主管、检测员冻结界面。

## 错误处理

- Web 写请求继续要求 CSRF。
- 打回和其他可重试写操作同时要求 `Idempotency-Key`。
- 并发冲突返回 409 和当前版本，前端提示刷新。
- 跨厂访问返回 403。
- 已退役、未启用或版本不一致的 Managed Form 返回 409，不接受过期提交。
- 厂长移动端 Bamboo 请求返回 403，并提示改用 Web 厂长端。

## 测试与验收

- 确认 `frontend/apps/web/src/mobile/**` 无改动。
- Managed Form 从管理员启用到移动端填写提交形成完整端到端测试。
- Web 和移动端读取同一通知、生产记录、工资事实。
- Web 知悉后同一通知状态立即更新。
- 厂长 Web 与主管移动端重复使用同一幂等键只产生一条打回。
- 两端基于相同旧版本同时打回时，仅一个成功，另一个返回版本冲突。
- 厂长移动端 Bamboo 请求被拒绝，工人、主管、检测员现有回归测试继续通过。
- `/plant/**` 页面不再读取旧的并行厂长表族。

## 非目标

- 不新增厂长以外角色的 Web 功能。
- 不改造工人、主管和检测员的移动端 UI。
- 不重新设计 Bamboo 工序状态机。
- 不删除财务或管理员仍在使用的账本、工资治理及通知表。
