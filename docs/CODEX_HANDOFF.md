# Codex 跨账户协作交接

最后更新：2026-07-14

仓库：`git@github.com:lhh666-6/auto-decte.git`

工作分支：`modular-architecture`

功能与交接基线：`66a90fd`（实际开始工作时以远程分支最新 `git log -1` 为准）
工作目录：`D:\半自动表单检测系统\.worktrees\modular-architecture`

## 一分钟分支摘要

- 唯一集成分支：`modular-architecture`；不要在 `main` 或历史 `phase-*` 分支继续当前任务。
- 已完成：React 审核工作台基础、真实队列、模板识别后端、模板中心 Task 1–5（模板库、只读预览、复制调优、草稿恢复、预检发布）。
- 下一任务：实施计划 Task 6，完成字段选择、拖动、缩放和右侧属性编辑器。
- 随后任务：四个企业模板的幂等 seed；当前只有 MD 映射，不能在 React 中伪造已发布模板。
- 仍未产品闭环：审核草稿/退回/作废/确认并下一张、主数据 CRUD、模板化导出与重导、模板包和纸张实例、Tauri。
- 验证边界：2026-07-14 全量复测已通过；Python `147 passed`，Ruff、mypy、前端
  `18 passed` 与生产构建均通过。

## 队友开始前必须执行

```powershell
git fetch origin
git switch modular-architecture
git pull --ff-only origin modular-architecture
git status --short
```

预期 `git status --short` 无输出。不要在根目录 `main` 上开发，不要使用 `git reset --hard` 或覆盖其他人的提交。

给协作者 Codex 的首条指令可以直接使用：

```text
完整阅读 docs/CODEX_HANDOFF.md、PROGRESS.md 和模板中心实施计划。
只在 modular-architecture 分支工作，从 Task 6 开始。
不要重新实现 Task 1–5，不要修改 main 或删除历史分支。
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

## 已完成并已推送

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
- 受控图片导入；
- 真实队列 API 与侧栏计数：待分类、待复核、规则异常、可导出；
- 队列表单卡片可打开工作台；主数据入口不会再静默无响应。

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

### A. 下一任务：真正的模板画布编辑器（最高优先级）

计划中的 Task 6 尚未实现；中断时已停止子任务，工作树无半成品。

需要创建：

```text
frontend/apps/web/src/TemplateCanvasEditor_ds.tsx
frontend/apps/web/src/FieldInspector_ds.tsx
```

要求：

- 画布显示真实 A4/A5 比例、字段框、QR 安全区和四角标记；
- 点击字段高亮并打开右侧属性；
- 拖动与缩放使用现有 `moveRect` / `resizeRect`；
- 只在 pointer-up 时调用 `replaceField` 持久化；
- 安全区冲突保留旧坐标并显示中文原因；
- 属性编辑包含显示名、数据/输入类型、识别引擎、阈值和坐标；
- 删除字段需要确认；新增字段、预检和发布必须继续可用；
- `DRAFT`、`PREFLIGHT_FAILED`、`READY_TO_PUBLISH` 可编辑，发布终态只读；
- 响应式和键盘可用。

建议直接按计划文件 Task 6 执行，完成后做需求审查、代码质量审查、更新 `PROGRESS.md`、提交并推送。

### B. 四个通用模板尚未作为安装数据真正落库

文档已经定义四类模板：

- `PAYROLL_HOURLY`
- `PAYROLL_STANDARD_PIECE`
- `PAYROLL_FIXED_PRODUCTION_GRID`
- `PAYROLL_EQUIPMENT_PROCESS`

但新安装数据库不会自动拥有四个已发布模板。需要实现幂等 seed/import 命令或安装初始化流程，并配置真实字段、坐标、规则、导出映射和打印预览。不得在 React 中伪造已发布卡片。

### C. 模板包与打印批次未闭环

- 安全 ZIP 模板包导入/导出；
- manifest schema/hash/冲突检查和 ZIP Slip/压缩炸弹防护；
- print_batch 与每张纸唯一 sheet_instance_id 的实际生成、存储和重复提交拦截；
- 模板版本差异与效果对比。

### D. 审核工作台仍有功能缺口

- 保存草稿 API 与按钮；
- 退回、作废、更正原因；
- 原子 `confirm-and-claim-next`；
- 上一张/下一张和稳定队列筛选快照；
- 图片缩放、旋转、复位和字段裁切详情；
- 规则结果/字段组错误的真实 API；
- 导出后更正影响与 `REEXPORT_REQUIRED` UI；
- 人工分类页面和模板选择交互；
- 当前“规则异常”队列主要依赖现有状态，尚未接完整三阶段规则结果。

### E. 主数据仍是只读骨架

员工、工单、产品、工序没有 SQLite 持久化 CRUD/API/编辑页。当前入口只明确提示缺口。需要迁移、权限、审计、禁用/版本策略，并接入字段枚举和规则。

### F. 导出中心尚未产品化

- `export-map.json` 模板映射；
- 导出预览和 `XLSX_EXPORT` 真实任务 Handler；
- 公式注入防护验收；
- 不可变导出批次、授权下载、重导关系和导出状态队列；
- 数据表、统计图和筛选联动。

### G. 任务/桌面/生产化

- FORM_IMPORT、FORM_RECOGNITION、XLSX_EXPORT 尚未全部成为真实持久化 Handler；
- Tauri v2 壳、File/Camera/Scanner/Audio Ports 和 Windows 安装包；
- 可信企业认证、生产 Worker、PostgreSQL/NAS-S3/Qdrant Adapter；
- 模板包签名、生产日志脱敏和正式升级/恢复演练。

## 队友建议执行顺序

1. 完成计划 Task 6：画布编辑器与字段属性检查器；
2. 完成计划 Task 7：全量验证、浏览器生命周期验收和进度记录；
3. 实现四个模板的幂等安装 seed，并用企业历史表格校准字段/坐标；
4. 补审核草稿、退回/作废、人工分类和 `confirm-and-claim-next`；
5. 实现主数据 CRUD；
6. 实现模板化导出中心与重导闭环；
7. 实现模板包、打印批次/纸张实例；
8. 最后做 Tauri、真实设备和生产 Adapter。

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
