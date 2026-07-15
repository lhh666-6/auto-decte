# Codex 跨账户协作交接

最后更新：2026-07-15

仓库：`https://github.com/lhh666-6/auto-decte.git`

工作分支：`modular-architecture`

本地功能基线：`5b9de49 feat: add versioned master data center`
当前工作目录：`E:\codex\auto-decte`

## 当前目标终止与转接状态

- 2026-07-15，用户要求终止当前目标，后续任务转交另一位协作者；本协作者不再继续实现新功能。
- 功能代码停在主数据阶段完成后：模板化导出与重导阶段只做了只读现状审计，**没有新增测试、迁移、API 或页面代码**。
- 本次交接包含以下 7 个功能/修复提交，以及最后一个纯文档交接提交；用户已授权在总结完成后将它们全部推送到 `origin/modular-architecture`：
  - `5b9de49 feat: add versioned master data center`
  - `bd54ab3 feat: harden template and import lifecycle`
  - `a20e295 feat: complete review workbench workflow`
  - `3ed353c feat: install built-in payroll templates`
  - `8564206 docs: record template studio completion`
  - `a8374b6 feat: add editable template draft canvas`
  - `7293ea3 fix: restore least-privileged local identity`
- 最终交接完成后，本地与 `origin/modular-architecture` 应指向同一提交；另一台机器或新 clone 的协作者可以直接从远端继承全部成果。
- 推送前必须先 `git fetch origin` 并确认没有分叉；推送后用 `git rev-parse HEAD`、`git rev-parse origin/modular-architecture` 和 `git status --short --branch` 复核。

## 一分钟分支摘要

- 唯一集成分支：`modular-architecture`；不要在 `main` 或历史 `phase-*` 分支继续当前任务。
- 已完成：React 审核工作台基础、真实队列、模板识别后端、模板中心 Task 1–5（模板库、只读预览、复制调优、草稿恢复、预检发布）。
- 已完成：实施计划 Task 6，字段选择、拖动、缩放、键盘移动和右侧属性编辑器已落地。
- 已完成：四个企业模板已通过幂等安装流程真实落库，包含字段、规则、导出目标和打印产物。
- 已完成：模板名称/用途元数据、草稿放弃删除和已发布模板退役；退役保留历史版本与打印产物。
- 已完成：审核草稿、同一审核人租约恢复、退回、作废、人工分类，以及事务内原子 `confirm-and-claim-next`。
- 已完成：员工、工单、产品、工序主数据 SQLite CRUD、搜索、权限、乐观版本、停用/恢复、独立审计及审核字段联动。
- 下一任务：模板化导出与重导；之后依次为模板包和纸张实例、持久化任务 Handler、Tauri。
- 验证边界：2026-07-15 最近一次全量复测通过；Python `183 passed`，Ruff、mypy（122 个源文件）、前端
  `34 passed` 与生产构建均通过；浏览器完成创建、更新、停用、筛选停用项、恢复及四版本审计自验。
- 重复图片导入会返回已有表单及状态，不再创建失败任务；开发环境管理员可重新启用已作废表单，或通过带二次确认的入口彻底清除本地测试数据。生产环境不暴露测试管理接口。
- Alembic `005` 仅对 `ORIGINAL_IMAGE` 保持 SHA 全局唯一；`006` 新增主数据记录与审计表。校正图和字段裁切允许重复内容。处理异常会失败任务并回滚半成品，当前本地标准计件测试表已修复为 20/20 字段。

## 队友开始前必须执行

同一工作目录接手：

```powershell
Set-Location E:\codex\auto-decte
git switch modular-architecture
git status --short
git log -8 --oneline
git rev-list --count origin/modular-architecture..HEAD
```

预期 `git status --short` 无输出；最终推送完成后分支领先数为 0，本地 HEAD 与 `origin/modular-architecture` 一致。不要 reset、rebase 或覆盖交接提交。

远程/新 clone 接手时执行：

```powershell
git fetch origin
git switch modular-architecture
git pull --ff-only origin modular-architecture
git status --short
```

预期 `git status --short` 无输出。不要在 `main` 或历史 `phase-*` 分支开发，不要使用 `git reset --hard` 或覆盖其他人的提交。

给协作者 Codex 的首条指令可以直接使用：

```text
完整阅读 docs/CODEX_HANDOFF.md、PROGRESS.md 和模板中心实施计划。
只在 modular-architecture 分支工作，从模板化导出与重导中心开始。
不要重新实现模板中心、seed 或已完成的审核闭环，不要修改 main 或删除历史分支。
完成后运行定向验证、更新 PROGRESS.md、提交并推送 modular-architecture。
```

## 产品目标

系统目标是 Windows 本地优先的模板驱动纸质表单闭环：

```text
模板设计 → 不可变发布 → 打印 → 图片导入 → QR 分类
→ ArUco 校正 → 字段裁切 → OCR/OMR 候选 → 人工审核
→ 版本/审计 → XLSX 导出 → 更正后重导 → 全链路追溯
```

前端采用同一套 React Feature，Web 与未来 Tauri 桌面壳共用。SQLite、本地证据、任务系统和识别实现必须经 Port/Adapter 隔离。

权威需求与计划：

- `docs/superpowers/specs/2026-07-13-template-driven-paper-form-closed-loop-design.md`
- `docs/superpowers/specs/2026-07-13-template-center-studio-design.md`
- `docs/superpowers/plans/2026-07-13-template-center-studio-implementation.md`
- `docs/design/review-workbench-style.md`
- `PROGRESS.md`

## 已完成功能（推送状态见顶部）

### 1. 稳定后端闭环基础

- 图片证据导入、SHA-256 去重和不可变证据；
- 人工确认/更正、RecordVersion、AuditEvent、乐观版本；
- 图像质量、二维码分类、透视校正、数字模板与 OMR 基础能力；
- 规则校验、查询追溯、XLSX 四工作表导出；
- 默认关闭的 AI Adapter、本地相似检索；
- SQLite UoW、审核 Lease、任务状态机、SSE、备份/完整性和 JSON 日志骨架。

### 2. React 审核工作台

- React/Vite Web Shell 已可运行，当前地址通常为 `http://127.0.0.1:5175/`；
- 左图右表、字段框/表格选中联动、候选值、受控证据读取；
- 审核锁获取/续租/释放及确认；
- 同一审核人刷新页面后可恢复并续期现有审核锁；
- 受控图片导入；
- 真实队列 API 与侧栏计数：待分类、待复核、规则异常、可导出；
- 队列表单卡片可打开工作台；主数据入口不会再静默无响应。
- 草稿保存与重载恢复，不会提前改变正式记录版本；
- 退回会清除草稿和租约并进入重新采集，作废会追加不可变 `VOIDED` 版本；
- 确认时执行模板必填/枚举/数值规则，并在一个事务内释放当前锁、按
  `priority DESC, created_at ASC, form_id ASC` 领取下一张；
- 二维码失败时只列出已发布模板，人工分类写审计并创建幂等 `FORM_RECOGNITION` 任务。

### 3. 模板识别后端

- TemplateVersion 生命周期、A4/A5 标准坐标和不可变发布；
- `IFD|template_key|version|checksum` QR；
- `SHEET|batch|sequence|checksum` 实例码格式；
- ArUco 10/11/12/13 打印标记和透视校正；
- 标准画布、字段裁切证据、RecognitionAttempt、候选生成；
- 字段识别引擎与自动预填阈值；
- QR 失败进入 `NEEDS_CLASSIFICATION`，不静默猜模板；
- 人工模板分配 API。

### 4. 模板中心：Task 1–5 已完成

完成提交范围：`0cf97fb` 至 `443fcfb`。

- 草稿字段可替换/删除；发布、停用、退役版本不可修改；
- 模板库稳定查询、版本详情、克隆调优和字段 PATCH/DELETE API；
- 完整字段/页面/父版本/打印件 DTO，不返回内部 URI；
- TypeScript TemplateApi 与画布几何模型；
- QR 安全区碰撞拒绝、画布边界限制、可编辑生命周期判断；
- 模板中心首先进入真实模板库，不再打开参数毛坯页；
- 搜索、状态筛选、诚实空状态、创建空白草稿；
- 发布模板只读预览；只有点击“基于此模板调优”才克隆草稿；
- 模板库同时显示发布版本与活动草稿，草稿可恢复；
- 恢复原有字段添加、预检、发布工作流；
- 错误重试、无障碍提示、桌面/平板/手机响应式布局。

最近验证：

- 模板 API 定向测试：`7 passed`；
- 前端状态/API 定向测试：`10 passed`；
- 前端 `npm run typecheck` 与 `npm run build:web` 通过；
- 本节记录时全量 Python 套件曾有 2 个 identity 默认值断言失败；该问题已于
  2026-07-14 通过恢复最小权限默认身份解决，并经全量回归验证。

## 当前明确未完成

### A. 模板中心、四模板 seed 与生命周期管理已完成

- Task 6 提交：`a8374b6`；新增真实 A4/A5 可编辑画布和字段属性检查器。
- 支持字段选择、拖动、缩放、键盘移动、显式保存和确认删除。
- QR、SHEET、ArUco 与打印边缘保护区会阻止非法落点；坐标输入使用同一保护规则。
- 字段变化重置预检状态，只有 `READY_TO_PUBLISH` 可发布，发布后编辑控件只读。
- 四个模板由 FastAPI/Streamlit 组合根幂等安装为真实 `PUBLISHED` V1，首次生成 PNG/PDF；
  重复执行不新增版本，内容冲突整体拒绝，基础打印产物缺失或损坏时自动修复。
- 字段规则与稳定 XLSX 导出目标已纳入领域、存储、API 和设计器属性检查器。
- Alembic `004` 新增模板名称与用途元数据；模板键保持不可变，创建时和创建后均可改名称。
- 草稿、预检失败和待发布版本可放弃删除；有活动草稿时禁止退役，必须先明确放弃草稿。
- 发布模板不物理删除；退役会停止所有发布版本用于新分类，但保留历史版本、二维码解析依据和打印产物。
- 2026-07-15 本地全量质量门与新数据库浏览器验收通过；尚未推送远端。

### B. 模板包与打印批次未闭环

- 安全 ZIP 模板包导入/导出；
- manifest schema/hash/冲突检查和 ZIP Slip/压缩炸弹防护；
- print_batch 与每张纸唯一 sheet_instance_id 的实际生成、存储和重复提交拦截；
- 模板版本差异与效果对比。

### C. 审核工作台剩余增强项

- 显式上一张/下一张导航和跨筛选条件的队列快照；
- 图片缩放、旋转、复位和字段裁切详情；
- 规则结果/字段组错误的真实 API；
- 导出后更正影响与 `REEXPORT_REQUIRED` UI；
- 当前“规则异常”队列主要依赖现有状态，尚未接完整三阶段规则结果。
- `FORM_RECOGNITION` 任务已经持久化创建，但仍需生产 Worker/Handler 实际消费。

### D. 主数据 CRUD 已完成

- `employees`、`work-orders`、`products`、`processes` 共用版本化 SQLite 存储和稳定 API；编码创建后不可修改，也不提供物理删除。
- 管理员可以新建、编辑、停用和恢复；业务角色可读。写入使用修订号/`If-Match` 乐观锁，每次变化写独立审计快照和原因。
- React 主数据中心支持目录切换、搜索、显示停用项、JSON 扩展属性、版本保存及审计轨迹。
- 模板字段的 `master_data_source` 会返回有效下拉项；前端即时校验，后端确认时再次拒绝未知或停用编码。

### E. 导出中心尚未产品化

- 已有可复用基础：`ExportForms` 可同步筛选已确认记录，`XlsxExporter` 可生成“正式数据/异常与复核/汇总/导出说明”四工作表，`ExportBatch` 已保存文件路径、SHA-256 和 `(form_id, record_version)`；导出后更正会进入 `REEXPORT_REQUIRED`，旧文件不会覆盖。
- 当前没有导出 API Router、React 导出中心或 `XLSX_EXPORT` Handler；现有导出仍主要由 Streamlit 页面同步调用。
- `export-map.json` 模板映射；
- 导出预览（包括排除记录和字段级错误）和 `XLSX_EXPORT` 真实持久化任务 Handler；
- 公式注入防护验收；
- 扩充不可变导出批次的模板版本/映射版本/过滤快照，增加授权下载、`supersedes_batch_id` 重导关系和导出状态队列；
- 数据表、统计图和筛选联动。

建议下一位先写失败测试固定这些边界，再迁移数据库和实现 API；不要直接从页面或同步 Streamlit 按钮开始。

### F. 任务/桌面/生产化

- FORM_IMPORT、FORM_RECOGNITION、XLSX_EXPORT 尚未全部成为真实持久化 Handler；
- Tauri v2 壳、File/Camera/Scanner/Audio Ports 和 Windows 安装包；
- 可信企业认证、生产 Worker、PostgreSQL/NAS-S3/Qdrant Adapter；
- 模板包签名、生产日志脱敏和正式升级/恢复演练。

## 队友建议执行顺序

1. 确认顶部列出的提交及最终交接文档提交已存在于 `origin/modular-architecture`；
2. 实现模板化导出中心与重导闭环；
3. 实现模板包、打印批次/纸张实例；
4. 补齐 FORM_IMPORT、FORM_RECOGNITION 等其余持久化任务 Handler；
5. 完成审核工作台高级图像工具、规则结果面板和导出影响 UI；
6. 最后做 Tauri、真实设备、生产认证与生产 Adapter。

每个步骤都要：定向测试 → 需求审查 → 代码质量审查 → 更新 `PROGRESS.md` → 小提交 → 推送 `modular-architecture`。

## 基本完成后的验收方案

### 自动化门槛

```powershell
uv run python -m pytest -q
uv run python -m ruff check .
uv run python -m mypy app config
Set-Location frontend
npm run test
npm run build:web
```

当前质量门已无已知红项；后续变更仍须重新运行全部命令，正式验收报告不得引用过期结果。

### 浏览器功能验收

至少连续完成：

```text
选择发布模板 → 只读预览 → 克隆调优 → 移动/缩放字段
→ 预检 → 发布 → 打开打印件 → 上传打印/拍摄图片
→ QR 分类 → 校正/裁切/候选 → 人工审核 → 确认
→ 导出 XLSX → 更正 → 标记重导 → 追溯原图和模板版本
```

### 真实样本验收

准备每类模板至少 10–15 张，总计至少 40–60 张，覆盖不同手机、距离、旋转、阴影、折痕、黑白打印、打印缩放、QR 污损、角标遮挡、越格数字、OMR 不清、重复拍摄和导出后更正。

目标：

- QR 成功样本模板分类正确率 ≥99%；
- QR 失败 100% 进入待分类，静默猜错 0 次；
- 透视校正和字段覆盖率 ≥98%；
- 自动预填字段精确率 ≥99%；
- 阻断规则自动放行 0 次；
- 模板发布、人工分类、确认和导出审计率 100%；
- 连续审核 30 张无流程中断；
- 任一 XLSX 值能追溯到记录版本、字段、模板版本和原始证据。

## 本地运行

```powershell
# 后端
uv run python -m uvicorn app.api.main:create_app --factory --host 127.0.0.1 --port 8000

# 前端（另一个终端）
Set-Location frontend
npm run dev:web
```

当前机器最近使用前端 `http://127.0.0.1:5175/`，后端 `http://127.0.0.1:8000/`。

## 协作注意事项

- `_ds` 是贡献来源标识，不是外部部署契约；保持 `app.api.main` 等公共入口稳定；
- 不提交 `.env`、SQLite、真实图片/录音、导出文件、`.runtime`、缓存和企业敏感数据；
- React Feature 只能通过 API Client/Shell Ports，不得直连数据库、本地路径或 Tauri API；
- 发布模板不可编辑，调优必须克隆新版本；
- AI、向量和音频关闭后核心流程仍必须运行；
- 不要把局部定向测试写成“整个系统已验证”。
