# 当前任务：工业表单前端重建与交互优化

状态：已完成范围确认，等待队友按实施计划开发

优先级：当前唯一开发方向

目标分支：`modular-architecture`

## 唯一执行入口

后续开发必须严格按 [2026-07-17-frontend-rebuild-implementation.md](superpowers/plans/2026-07-17-frontend-rebuild-implementation.md) 的任务 1—16 顺序进行。该计划已经明文列出每项任务允许读取的文件、要修改的文件、测试先行步骤、命令、预期结果、验收标准和提交节点。执行者不需要扫描整个项目，也不得跳过测试或自行扩大后端范围。

现有界面按钮、状态、API 语义和完整闭环见 [FRONTEND_INTERACTION_GUIDE.md](FRONTEND_INTERACTION_GUIDE.md)。本文件后续内容保留人工试用阶段发现的问题和已确认产品方向，作为前端重建的业务依据。

产品方向的唯一来源是用户提供的 `frontend_rebuild_summary.md`。实施计划只负责把它拆成工程步骤，不得加入计划外产品功能；如实施计划与原文冲突，以原文为准并停止冲突任务，等待人工确认。

开发重点和顺序不得调整：

1. 第一阶段先完成核心审核闭环。
2. 第二阶段再完成统一应用外壳、路由和视觉语义。
3. 第三阶段最后压缩模板、基础数据和导出模块。

## 本轮已批准的开发方向

1. 以统一双栏审核工作台为核心，建立图片字段框与电子表格字段行的双向联动。
2. 三类任务“待确认表单类型、待核对、待重新拍照”共用同一工作台骨架。
3. 加入图片缩放、滚轮、拖动、旋转、复位、原图/校正图和字段裁片查看。
4. 分类后使用现有任务查询接口原地显示识别进度，不跳出工作台。
5. 建立统一浏览器路由和应用外壳，一级导航固定为审核工作台、模板中心、基础数据、导出数据。
6. 使用中文业务语言替代默认技术状态码；技术 ID、哈希和状态码保留在追溯详情。
7. 模板、基础数据和导出模块按实施计划压缩与业务化，不改变后端契约。

## 明确阻塞：重新拍照的永久追溯

现有 `POST /api/v1/imports` 会为新照片创建新表单，尚无生产接口把新照片作为 `RECAPTURE_REQUIRED` 原表单的 replacement evidence 并永久保存新旧证据关系。因此纯前端阶段只能重建待重拍页面、展示旧证据和退回原因，并诚实说明上传新照片会创建新表单；禁止使用浏览器内存或 `localStorage` 冒充永久追溯。真正闭环必须另立后端任务并获得明确授权。

独立后端任务必须同时提供：

- 为原表单提交 replacement evidence 的生产接口；
- 使用新证据运行重新识别并返回可查询任务；
- 永久保存 old/new evidence linkage；
- 为替换、重新识别和关联结果写入不可变审计事件。

## 前期问题收集目标（已完成范围确认）

在不修改业务代码的前提下，用现有系统和工厂原始工资表找出产品适配、纸面设计、打印、识别、审核和本地操作流程中的问题，为后续人工决策提供证据。本阶段不把讨论中的方向直接实现为功能。

```text
读取原始工资表并归纳真实流程
→ 用现有系统创建/导出/打印模板
→ 导入真实或接近真实的拍照样本
→ 记录权限、版面、填写、识别和审核问题
→ 形成问题清单与样本证据
→ 人工确定下一阶段实施优先级
```

## 已发现问题

1. 本地应用没有登录界面，但默认权限会阻止图片导入和模板创建；这与单用户试用流程冲突。
2. 当前演示模板保留过多自由手写空间，无法充分限制工人填写方式，也增加 OCR/OMR 难度。
3. 当前页面模型只允许 A4/A5，不能表达工厂常见的不定尺寸横条和节纸裁切方式。
4. 模板设计器已有拖动和缩放，但缺少面向业务的小模块、毫米网格吸附和模块最小物理尺寸约束。
5. 二维码生成、PNG/PDF 导出、读取和精确版本绑定已经可用，但现场打印/拍照可靠性尚未量化。
6. 工号识别与员工库比对、姓名人工核对以及“未知工号禁止正式导出”的产品流程尚未闭环。
7. 当前模板视觉结构没有充分继承原始计时、计件和复杂生产明细工资表的实际流程。

## 已确认但暂不实现的产品方向

- 采用“计时、简单计件、复杂生产明细”三类母版，车间只配置岗位选项、规格、等级、单位、单价、异常代码和固定行数。
- 支持任意毫米宽高、横竖方向、A4/A5 预设和一页多联裁切；横条表格是正常形态，不强制适配单张 A5。
- 使用受约束小模块：数字方格、单选方块、姓名/签名线、固定明细行、异常短说明、二维码安全区和静态说明。
- 模块采用毫米网格吸附，可以移动、调宽、换行和增删，但必须满足最小填写尺寸、打印边距和识别安全区。
- 工人只填工号、姓名和必要数量；记录人填写生产数据；质检/主管填写等级和考评。纸面使用黑白边框、编号和文字区分责任，不依赖彩色打印。
- 工号暂按可配置位数的纯数字逐格识别并与员工库匹配；姓名不用于自动猜测身份，只供人工核对。
- 发布模板锁定纸张尺寸、模块坐标、字段类型和识别规则；修改生成新版本。二维码失败时人工选择精确模板版本，不自动猜测。
- 纸张过小，无法容纳二维码、四角定位标记和最小填写格时，禁止发布并标出冲突，不自动缩小。
- 异常使用固定代码；代码 99 允许一行短说明。完整标准另行张贴并版本化，不在每张表上重复长文本。

## 当前验证方案

1. 从根目录现有工作簿中各选择计时、简单计件和复杂生产明细的代表表，不读取开发说明文档。
2. 每类先制作少量接近真实尺寸的纸面样张，记录纸张毫米尺寸、打印机、打印比例和裁切方式。
3. 使用不同手机、方向、距离、光线和纸张状态拍照，覆盖正常、模糊、倾斜、折痕、阴影、缩放和二维码污损。
4. 验证二维码分类、透视校正、字段裁切、数字格、单选框、人工分类和审核操作，并保留失败样本。
5. 所有问题记录“样本、复现步骤、影响、临时绕行和建议优先级”，不在验证过程中顺手扩展功能。
6. 人工评审问题清单后，再决定是否进入自定义尺寸、模块搭建器、人员匹配或权限体验的实施阶段。

## 本阶段非目标

- 不实现自定义纸张尺寸或新的纸面渲染器。
- 不实现小模块组件库或网格吸附。
- 不修改权限矩阵、默认身份或增加登录界面。
- 不新增工号自动匹配、姓名 OCR 或工资计算规则。
- 不重做现有模板、识别、审核、导出或主数据模块。
- 不在问题证据不足时承诺现场识别准确率。

## 已完成的上一任务

“模板化导出与重导闭环”已经完成；当前 HEAD 为 `35c1243`，最近全量验证为 Python `264 passed`、前端 `53 passed`、Ruff/mypy/类型检查和生产构建通过。本轮另对二维码与模板链路执行定向验证，结果为 `26 passed`。

以下内容作为已完成任务的范围和验收基线保留，不再代表当前开发授权。

## 已完成导出任务的原目标（历史保留）

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

## 已完成导出任务范围（历史保留）

1. 增加导出预览，返回拟包含记录、排除记录及字段级/表单级排除原因，不生成正式文件。
2. 以模板版本中的 `ExportTarget(workbook, worksheet, business_column)` 为稳定映射，不依赖 UI 显示名。
3. 创建持久化、幂等的 `XLSX_EXPORT` 任务，并通过现有任务状态/SSE 报告进度；失败不得留下成功批次或半成品文件。
4. 扩展不可变导出批次，至少保存模板版本、映射版本/快照、筛选快照、包含的 `(form_id, record_version)`、文件 SHA-256、操作者、时间和 `supersedes_batch_id`。
5. 提供导出批次列表、详情和授权下载 API；API 不得返回服务器绝对路径或内部 URI。
6. 对所有可能作为文本写入 XLSX 的值实施公式注入防护，覆盖 `= + - @` 开头文本。
7. 已导出记录更正后保持 `REEXPORT_REQUIRED`；重导生成新文件和新批次，不覆盖旧文件，并显式关联被替代批次。
8. 实现 React 导出中心：筛选、预览、创建任务、进度、批次历史、下载和需要重导提示。
9. 补齐 API、应用、存储、导出安全、重导和前端契约测试；更新 `PROGRESS.md` 与本交接文件。

## 已完成导出任务相关文件（历史保留）

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

## 已完成导出任务原冻结边界（历史保留）

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

## 已完成导出任务验收标准（历史保留）

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

## 已完成导出任务验证命令（历史保留）

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
