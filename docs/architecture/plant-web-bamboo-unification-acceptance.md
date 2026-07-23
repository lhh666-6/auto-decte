# 厂长 Web 与竹丝业务统一验收

验收日期：2026-07-23

- 厂长仅使用 Web 工作区；移动端竹丝接口对厂长统一返回
  `PLANT_MANAGER_WEB_ONLY`。
- `/api/v1/plant/**` 的生产记录、检测、消息、人员调动和工资均读取既有
  Bamboo 数据；不再读取并行的财务投影、业务任务、工资计算结果或管理通知。
- 管理员启用的电子表单可由所属工厂移动端获取 Schema 并真实提交。
- 厂长可按分选、浸胶、干燥环节选择打回；所有客户端共用同一条打回命令。
- 打回命令使用 `expected_revision`、`Idempotency-Key`、数据库唯一约束和事务锁。
  两个 Web 会话并发打回同一版本时仅一个成功，另一个返回
  `REVISION_CONFLICT`。
- 跨厂调动仍要求来源厂长、目标厂长同时同意，再由管理员最终执行。
- Alembic 最新版本为 `028`。

验证结果：

- 聚焦后端验收：`46 passed`。
- Web 全量 Vitest：`59 files / 292 passed`。
- Ruff、Mypy、Web TypeScript typecheck、移动端目录边界检查全部通过。
