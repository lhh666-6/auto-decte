# 阶段交接：模板、审核与主数据收尾

日期：2026-07-16

分支：`modular-architecture`

收尾前远程 HEAD：`08daef7`

## 本阶段范围

本阶段接收并复核了队友从 `7293ea3` 到 `2a634d6` 的 8 个提交，补充了旧数据库启动兼容修复 `f050c7e`，并通过 `08daef7` 更新长期交接文档。本次阶段结束只新增状态/任务/决策/交接文档，不继续开发新功能。

## 本阶段具体修改

### 1. 最小权限身份

- 默认本地身份恢复为 `local-operator/OPERATOR`。
- 模板创建、发布、退役和主数据写入仍要求显式高权限。
- 相关提交：`7293ea3`。

### 2. 可视化模板设计器

- 新增 A4/A5 标准比例画布和字段图层。
- 支持选择、拖动、缩放、方向键移动、`Alt+方向键` 调整大小。
- 新增右侧字段属性检查器，统一保存字段坐标、规则、识别引擎、阈值和导出目标。
- QR、SHEET、ArUco 和打印边缘保护区阻止非法落点。
- 相关提交：`a8374b6`、`8564206`。

### 3. 四个企业模板

- 幂等安装 `PAYROLL_HOURLY`、`PAYROLL_STANDARD_PIECE`、`PAYROLL_FIXED_PRODUCTION_GRID`、`PAYROLL_EQUIPMENT_PROCESS`。
- 模板包含公共字段、岗位字段、固定明细行、规则、导出目标和 PNG/PDF 打印产物。
- 同键同版本不同内容由严格 seed 安装整体拒绝。
- 相关提交：`3ed353c`。

### 4. 审核工作台事务闭环

- 增加审核草稿和刷新恢复。
- 增加 Lease 续期、退回、作废、人工分类和具体字段规则错误。
- `confirm-and-claim-next` 在同一事务内确认当前表单并领取下一张。
- 审核页面优先显示校正图，标准坐标不再错误覆盖低分辨率原图。
- 相关提交：`a20e295`。

### 5. 模板和导入生命周期加固

- 模板名称/用途可编辑，发布版本只读，草稿可放弃，发布模板通过退役保留历史。
- 原图 SHA 全局唯一；派生校正图和字段裁切允许重复。
- 重复图片返回已有表单和可执行动作，不再制造失败任务。
- 导入处理异常会回滚半成品并清理孤立派生文件。
- 相关提交：`bd54ab3`。

### 6. 主数据中心

- 新增员工、工单、产品和工序 SQLite CRUD。
- 使用稳定编码、revision/If-Match 乐观锁、停用/恢复和独立审计。
- React 主数据中心支持搜索、显示停用项、编辑属性和查看审计。
- 模板字段可以绑定主数据来源；审核页以下拉选择，后端确认时再次校验。
- 相关提交：`5b9de49`。

### 7. 拉取后旧库兼容修复

- 空 `alembic_version` 表不再误判为已迁移数据库，避免重复执行 001 建表。
- 旧库同名 V1 模板与内置 seed 冲突时，应用保留旧模板、记录警告并继续启动。
- API 兼容入口测试改用临时数据目录，不再读取协作者真实数据库。
- 相关提交：`f050c7e`。

### 8. 永久交接文档

- 更新 `PROGRESS.md` 和 `docs/CODEX_HANDOFF.md`，记录队友提交、复核结果、兼容修复和剩余任务。
- 新增 `docs/CURRENT_STATUS.md`、`docs/NEXT_TASK.md`、`docs/DECISIONS.md` 和本文件。
- 相关提交：`08daef7` 及本次文档收尾提交。

## 测试结果

2026-07-16 在 `f050c7e` 后完成：

- `uv run python -m pytest -q` → `185 passed`。
- `uv run python -m ruff check .` → 全部通过。
- `uv run python -m mypy app config` → 124 个源文件无问题。
- `npm run test` → 6 个测试文件，`34 passed`。
- `npm run typecheck` → 通过。
- `npm run build:web` → 生产构建通过。
- 使用当前真实旧库调用 `app.api.main:create_app` → API 成功创建，13 条路由；内置模板冲突被记录为警告而非启动失败。

本轮没有在最新拉取状态下重新执行完整浏览器人工闭环，因此不得将队友 2026-07-15 的浏览器自验描述为本轮重新验收。

## 遗留风险

1. 模板化导出仍停留在同步服务基础，没有 API、React 页面、持久化 Handler、授权下载和完整批次快照。
2. XLSX 公式注入防护没有实现或测试。
3. 旧库同名模板冲突采取“保留并告警”，因此该数据库不会自动获得完整四模板 seed；需后续显式版本迁移。
4. `FORM_RECOGNITION` 等任务可以持久化，但生产 Worker/Handler 尚未完整消费。
5. 审核高级图像工具、完整三阶段规则面板和导出影响 UI 未完成。
6. 中文 OCR 未接入；真实样表量化验收未完成。
7. 模板 ZIP、打印批次、纸张实例和重复拍摄识别未完成。
8. Tauri 与真实设备接入未完成。

## 下一位的唯一首要任务

阅读 [NEXT_TASK.md](../NEXT_TASK.md)，实现“模板化导出与重导闭环”。不要重新实现模板画布、四模板 seed、审核事务或主数据中心，不要修改 `main` 或历史迁移。

开始前：

```powershell
git fetch origin
git switch modular-architecture
git pull --ff-only origin modular-architecture
git status --short
```

预期工作树干净。完成下一阶段后必须更新 `PROGRESS.md` 和本目录中的新日期交接文件，再提交并推送 `modular-architecture`。
