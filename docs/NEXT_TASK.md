# 下一任务：模板化导出与重导闭环

状态：未开始

优先级：下一项唯一功能任务

目标分支：`modular-architecture`

## 目标

在不改变模板设计、识别和审核语义的前提下，将现有同步四工作表导出升级为可预览、可追溯、可授权下载、可重导的模板驱动服务：

```text
筛选已确认表单
→ 导出最终校验与预览
→ 创建幂等 XLSX_EXPORT 任务
→ 按模板字段 export_target 生成 XLSX
→ 保存不可变批次快照和 SHA-256
→ 授权下载
→ 更正后 REEXPORT_REQUIRED
→ 新批次显式 supersedes 旧批次
```

## 明确范围

1. 增加导出预览，返回拟包含记录、排除记录及字段级/表单级排除原因，不生成正式文件。
2. 以模板版本中的 `ExportTarget(workbook, worksheet, business_column)` 为稳定映射，不依赖 UI 显示名。
3. 创建持久化、幂等的 `XLSX_EXPORT` 任务，并通过现有任务状态/SSE 报告进度；失败不得留下成功批次或半成品文件。
4. 扩展不可变导出批次，至少保存模板版本、映射版本/快照、筛选快照、包含的 `(form_id, record_version)`、文件 SHA-256、操作者、时间和 `supersedes_batch_id`。
5. 提供导出批次列表、详情和授权下载 API；API 不得返回服务器绝对路径或内部 URI。
6. 对所有可能作为文本写入 XLSX 的值实施公式注入防护，覆盖 `= + - @` 开头文本。
7. 已导出记录更正后保持 `REEXPORT_REQUIRED`；重导生成新文件和新批次，不覆盖旧文件，并显式关联被替代批次。
8. 实现 React 导出中心：筛选、预览、创建任务、进度、批次历史、下载和需要重导提示。
9. 补齐 API、应用、存储、导出安全、重导和前端契约测试；更新 `PROGRESS.md` 与本交接文件。

## 相关文件

### 现有实现，应优先复用

- `app/application/export_forms.py`
- `app/adapters/export/xlsx.py`
- `app/modules/reporting/facade_ds.py`
- `app/domain/models.py`
- `app/domain/templates_ds.py`
- `app/adapters/database/models.py`
- `app/adapters/database/repositories.py`
- `app/modules/tasks/models_ds.py`
- `app/modules/tasks/service_ds.py`
- `app/infrastructure/tasks/sqlite_store_ds.py`
- `app/api/routers/tasks_ds.py`
- `app/api/main_ds.py`
- `app/modules/identity_access/models_ds.py`
- `app/modules/identity_access/policy_ds.py`
- `frontend/packages/api-client/src/index_ds.ts`
- `frontend/apps/web/src/App.tsx`
- `frontend/apps/web/src/styles.css`
- `frontend/features/exports-trace/README.md`
- `tests/integration/test_xlsx_export.py`

### 预计新增

- `alembic/versions/007_export_batches_ds.py`
- `app/api/routers/exports_ds.py`
- `app/api/schemas/exports_ds.py`
- `app/modules/reporting/models_ds.py`（如领域对象不能放入现有文件）
- `app/modules/reporting/handler_ds.py`
- `frontend/packages/api-client/src/exports_ds.ts`
- `frontend/apps/web/src/ExportCenter_ds.tsx`
- `frontend/apps/web/src/export-api.test.ts`
- `tests/api/test_exports_api_ds.py`
- 导出安全和 Handler 的定向测试文件

文件名可按现有项目规范微调，但不得复制出第二套导出服务或绕开 `reporting`、`tasks` 和 API Client 边界。

## 不允许修改的模块

除非为了修复被新增测试直接证明的回归，否则下一任务不得修改：

- 模板画布、属性检查器、模板库交互和四模板 seed：`TemplateCanvasEditor_ds.tsx`、`FieldInspector_ds.tsx`、`TemplateStudio_ds.tsx`、`seed_templates_ds.py`。
- 模板发布、复制调优、退役和预检语义。
- OpenCV、QR、ArUco、OCR/OMR、证据裁切和识别候选算法。
- 审核草稿、Lease、退回、作废和 `confirm-and-claim-next` 事务语义。
- 员工、工单、产品、工序主数据 CRUD 与审计语义。
- Alembic `001`–`006` 历史迁移；新结构只能新增 `007`，不得改写已发布迁移。
- Tauri、相机、扫描仪、音频、模板 ZIP 包和纸张实例功能。
- `main` 和历史 `phase-*` 分支；不得自行创建新的长期分支。

身份模块只允许增加导出下载所需的最小权限并将其授予明确角色，不得扩大本地默认操作者权限或改动其他角色能力。

## 验收标准

### 后端与安全

- `GET /api/v1/exports/preview` 只读，返回包含/排除明细和原因。
- `POST /api/v1/exports` 返回 `202 Accepted`、`task_id`、状态 URL 和事件 URL；相同 Idempotency-Key + 相同请求返回同一任务，不同请求返回冲突。
- 只有具备导出权限的身份可预览、创建和下载；默认 `OPERATOR` 不可导出。
- 下载响应不暴露 `file_path`、数据库对象、绝对路径或内部 URI。
- 导出只包含当前已确认且通过最终校验的 RecordVersion。
- 每一行可以通过批次、表单和记录版本反向追溯；批次保留模板/映射/筛选快照。
- 任一以 `= + - @` 开头的业务文本在 Excel 中不得被解释为公式。
- 任务失败时数据库无成功批次，输出目录无可误认成成功结果的半成品。
- 重导不会覆盖旧文件，新批次的 `supersedes_batch_id` 指向被替代批次。

### 前端

- “可导出”入口能打开真实导出中心，不再是无动作导航。
- 用户可筛选、预览、看到排除原因、创建导出、查看进度、查看历史并下载。
- `REEXPORT_REQUIRED` 有明确提示和重导动作。
- Web 前端不直接访问本地绝对路径、数据库或 Tauri API。

### 回归

- 模板设计、图片导入、审核事务、主数据和现有四工作表导出测试继续通过。
- `PROGRESS.md` 明文记录完成内容、测试数字、提交号、已知问题和下一任务。

## 验证命令

先运行定向验证：

```powershell
uv run python -m pytest tests/integration/test_xlsx_export.py tests/api/test_exports_api_ds.py -q
uv run python -m ruff check app tests
uv run python -m mypy app config
Set-Location frontend
npm run test
npm run typecheck
npm run build:web
```

提交前运行全量质量门：

```powershell
Set-Location "<仓库根目录>"
uv run python -m pytest -q
uv run python -m ruff check .
uv run python -m mypy app config
Set-Location frontend
npm run test
npm run build:web
```

还必须人工完成一次浏览器闭环：预览 → 创建导出 → 等待成功 → 下载 → 更正已导出表单 → 看到需重导 → 重导 → 验证旧文件仍存在且批次关联正确。
