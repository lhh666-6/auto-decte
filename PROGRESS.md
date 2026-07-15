# 开发进度与接力记录

> 本文件是两位 Codex 协作时的唯一明文接力状态。每次功能提交必须同步更新。

## P0 项目初始化

- 状态：已完成并推送
- 负责人：开发者 A（仓库所有者）
- 分支：`phase-0-bootstrap`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 建立 Python 3.11 项目配置和开发依赖
  - 建立环境配置、Streamlit 入口和测试框架
  - 建立 Git 忽略规则和协作说明
- 未完成：无
- 验证命令：`python -m pytest -v`；`python -m ruff check .`
- 验证结果：`1 passed`；Ruff `All checks passed!`；mypy `Success: no issues found in 5 source files`
- 最新提交：`d8d2b6c`
- 已知问题：无；已使用 GitHub SSH 推送
- 下一位操作：P0 合并后从最新 `main` 创建 `phase-1-manual-loop`

## P1 人工闭环

- 状态：已完成并推送
- 负责人：开发者 A（仓库所有者）
- 分支：`phase-1-manual-loop`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 领域实体、状态枚举和 Adapter 协议
  - SQLite 表单与不可变版本持久化
  - 原始图片 SHA-256、重复检测和只增证据存储
  - E99/自由说明/非常规更正/争议录音触发校验
  - 人工确认、更正、乐观版本检查和审计事件
  - 可操作的 Streamlit 图片导入与人工复核页面
- 未完成：无；仓库创建较晚，本阶段随已验证的 `main` 一并集成
- 验证命令：
  - `uv run python -m pytest -q`
  - `uv run python -m ruff check .`
  - `uv run python -m mypy app config`
  - `uv run python -c "from streamlit.testing.v1 import AppTest; ..."`
- 验证结果：`14 passed`；Ruff 全部通过；mypy 检查 22 个源文件无问题；Streamlit 无异常并显示“批量导入/人工复核”
- 最新提交：`71e8001`
- 已知问题：无；远程阶段分支 `phase-1-manual-loop` 已保留
- 下一位操作：已完成；后续阶段从最新 `main` 或 P6 集成分支继续

## P2 查询与导出

- 状态：已完成并推送
- 负责人：开发者 A（仓库所有者）
- 分支：`phase-2-query-export`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 基于 SQLite JSON 字段的表单/员工/工单组合精确筛选
  - 表单版本、证据和审计事件完整追溯
  - 正式数据、异常与复核、汇总、导出说明四工作表 XLSX
  - ExportBatch、文件 SHA-256、表单/版本反查标识
  - 已导出记录更正后自动标记 `REEXPORT_REQUIRED`
  - 唯一文件名导出，不覆盖旧 XLSX
  - Streamlit 查询追溯与导出页面
- 未完成：无；仓库创建较晚，本阶段随已验证的 `main` 一并集成
- 验证命令：`uv run python -m pytest -q`；`uv run python -m ruff check .`；`uv run python -m mypy app config`；Streamlit AppTest
- 验证结果：`18 passed`；Ruff 全部通过；mypy 检查 28 个源文件无问题；四个 UI 标签页加载无异常
- 最新提交：`943a174`
- 已知问题：无；远程阶段分支 `phase-2-query-export` 已保留
- 下一位操作：已完成；P3 已在独立分支实现并进入 P6 集成

## P3 图像与识别

- 状态：功能实现完成并通过合成测试，待真实样张指标验收
- 负责人：开发者 B（当前 Codex 会话代执行）
- 分支：`phase-3-recognition`
- 开始时间：2026-07-12
- 完成时间：功能代码 2026-07-12；真实样张验收未完成
- 已完成：
  - 模糊、过暗、强反光/空白图像质量检测与原因码
  - 透视校正和模板坐标字段裁切
  - 二维码优先模板分类与无二维码人工分类队列
  - 人工重新分类及 before/after/reason 审计事件
  - 单格数字 OpenCV 模板候选与空白保护
  - OMR 勾选、未勾选和歧义区间识别
  - FormField、RecognitionAttempt、字段裁切证据持久化
  - 识别 Attempt 只增保存，不覆盖人工确认版本
  - 追溯页展示识别 Attempt，Streamlit 图像分类页面
- 未完成：
  - 使用企业 30–50 张脱敏真实样张测量分类率、单数字准确率和整单正确率
  - 根据真实表单冻结三套模板坐标和定位点
- 验证命令：`uv run python -m pytest -q`；`uv run python -m ruff check .`；`uv run python -m mypy app config`；Streamlit AppTest
- 验证结果：`39 passed`；Ruff 全部通过；mypy 检查 37 个源文件无问题；六个 UI 标签页加载无异常
- 最新提交：`85eed55`
- 已知问题：当前数字识别为轻量合成字体基线，未达到真实生产样张准确率声明条件
- 下一位操作：提供三类模板和 30–50 张脱敏样张，在本分支补充 golden fixtures 与准确率报告

## P4 规则与审计

- 状态：已完成开发者 A 部分并推送，待开发者 B 审查
- 负责人：开发者 A 主导、开发者 B 审查
- 分支：`phase-4-rules-audit`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 必填、取值范围、数量闭合规则
  - 员工/工单主数据有效性规则
  - 重复表单、当前版本、重新导出和导出映射规则
  - 字段级错误码、严重性和中文失败原因
  - 导入、确认、更正和导出的审计完整性测试
  - Streamlit 规则异常页面
- 未完成：开发者 B 交叉审查；P3 接入后补充分类型/识别审计事件
- 验证命令：`uv run python -m pytest -q`；`uv run python -m ruff check .`；`uv run python -m mypy app config`；Streamlit AppTest
- 验证结果：`29 passed`；Ruff 全部通过；mypy 检查 30 个源文件无问题；五个 UI 标签页加载无异常
- 最新提交：`f6da6ec`
- 已知问题：远程阶段分支 `phase-4-rules-audit` 已保留；P3 审计覆盖已在集成分支补充
- 下一位操作：P6 已覆盖分类、识别、确认和导出组合审计

## P5 AI 与向量

- 状态：Demo 功能已完成并推送，已进入 P6 集成审查
- 负责人：开发者 B 主导、开发者 A 审查（当前 Codex 会话代执行）
- 分支：`phase-5-ai-vector`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 默认关闭且不发起外部请求的 AI Adapter
  - 严格结构化 AIReview/AISuggestion 合约
  - 证据列表非空、置信度范围和强制人工确认校验
  - 可注入 Provider，只接受严格 JSON 且校验 form_id
  - AI 建议独立持久化，不覆盖 RecordVersion
  - AI 建议审计事件与 AI 关闭端到端导出测试
  - 本地字符/二元组余弦相似检索，只返回引用
  - Streamlit AI 审查与相似异常检索页面
- 未完成：
  - 企业授权后的真实外部 AI API 配置与脱敏策略验收
  - 可选录音转写 Provider 和真实相似案例评估
- 验证命令：`uv run python -m pytest -q`；`uv run python -m ruff check .`；`uv run python -m mypy app config`；Streamlit AppTest
- 验证结果：`38 passed`；Ruff 全部通过；mypy 检查 38 个源文件无问题；六个 UI 标签页加载无异常
- 最新提交：`db9b7c1`
- 已知问题：本地向量索引为进程内 Demo 基线；外部 AI 默认关闭且未配置任何密钥
- 下一位操作：开发者 A 审查安全边界；未取得企业授权前保持 `FORM_DEMO_AI_ENABLED=false`

## P6 联调验收

- 状态：自动化联调完成，真实样张与现场指标待验收
- 负责人：两位开发者共同完成（当前 Codex 会话完成自动化部分）
- 分支：`phase-6-acceptance`
- 开始时间：2026-07-12
- 完成时间：自动化联调 2026-07-12；现场验收未完成
- 已完成：
  - 合并 P3 图像识别与 P5 AI/向量两条独立分支
  - 跨模块端到端验收：分类、识别、规则、确认、AI 关闭、检索、导出、追溯
  - README 启动、备份恢复、安全和 GitHub 接力说明
  - `docs/acceptance-report.md` 自动化证据与现场缺口报告
- 未完成：
  - 30–50 张脱敏真实样张技术指标
  - 100–300 张现场试点和人工基线对比
  - 企业 XLSX 模板、三种表单坐标和录音授权验收
- 验证命令：提交前运行全量 pytest、Ruff、mypy 和 Streamlit AppTest
- 验证结果：`49 passed`；Ruff 全部通过；mypy 检查 45 个源文件无问题；七个 UI 标签页加载无异常
- 最新提交：`6e53917`
- 已知问题：缺少源需求第 15 节列出的真实样张、金标准、主数据和企业模板
- 下一位操作：提供验收输入后补充受控 golden 数据集与真实指标，不得用合成测试替代

## P7 模块化架构实施

- 状态：已完成
- 负责人：Deepseek AI（当前会话）
- 分支：`modular-architecture`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 所有文件加 `_ds` 后缀命名统一
  - 建立 12 个模块目录和 Facade 入口（forms, evidence, recognition, review, rules,
    search, reporting, audit, tasks, identity_access, master_data, templates）
  - SQLite 连接工厂（WAL/外键/busy_timeout）和 UnitOfWork 事务边界
  - 身份角色权限：ADMIN/OPERATOR/REVIEWER/FINANCE/AUDITOR + 权限矩阵
  - ReviewLease 审核锁（获取/续租/过期/强制释放/审计事件）
  - Task 状态机（PENDING→RUNNING→SUCCEEDED/FAILED）+ 幂等键 + 重启恢复
  - FastAPI 骨架（/health/live, /health/ready, /api/v1/me）
  - API 路由：审核锁、确认（带 expected_version）、任务（SSE 进度推送）
  - Problem Details 错误格式化、request_id 全链路追踪
  - Alembic 迁移基线（11 表的完整迁移脚本）
  - BackupService（SQLite Online Backup + manifest）+ IntegrityChecker
  - 结构化日志（JsonLogFormatter）+ 错误追踪（LocalErrorTracker）
  - 前端契约骨架：Shell Ports（File/Camera/Scanner/Audio/Notification）、
    API Client Problem Details、Feature 模块 README
  - 架构契约测试（domain 零框架依赖、_ds 后缀合规、模块完整性）
  - 运维文档（migration.md, backup-recovery.md）
- 未完成：
  - 企业 SSO（替代 LocalIdentityProvider）
  - 生产级 Worker（替代 InProcessTaskRunner）
  - PostgreSQL/NAS/S3/Qdrant Adapter（替代 SQLite/本地文件）
  - React/Tauri 完整 UI（替代 Streamlit）
- 验证命令：
  - `uv run python -m pytest -q`
  - `uv run python -m ruff check .`
  - `uv run python -m mypy app config`
- 验证结果：`94 passed`；Ruff 全部通过；mypy 检查 107 个源文件无问题；Streamlit 七个 UI 标签页加载无异常
- 最新提交：`4c62e75`
- 已知问题：企业真实样张和现场指标仍需独立验收
- 下一位操作：提供验收输入后在真实环境下运行准确率脚本和性能基线
## Modular industrial architecture refactor (local branch only)

- Status: tasks 1–7 complete; task 8 (migrations, backup and integrity) is next.
- Working branch: `modular-architecture` in `.worktrees/modular-architecture`.
- Remote policy: local commits only. Do not push or deploy before the architecture acceptance task.
- Completed commits:
  - `b845e1b` — module entry points, settings, SQLite WAL/foreign-key/busy-timeout configuration.
  - `5e42263` — local identity provider and explicit role/permission policy.
  - `897e537` — UnitOfWork plus transactional review facade; audit failure rolls back versions.
  - `67ec488` — review leases, heartbeat/expiry, forced release reason, concurrency conflict and lease audit events.
  - `d495015` — persistent SQLite tasks, task-event sequencing, idempotency, retry, recovery and bounded in-process execution.
  - `c6a8bdb` — FastAPI app factory, request correlation, Problem Details, health and local identity endpoints.
  - `b289510` — versioned review leases, confirmation conflicts, task creation and resumable SSE events.
- Last verification: `76 passed`; `ruff check .` and `mypy app config` passed.
- Handoff: implement Task 8 from `docs/superpowers/plans/2026-07-12-modular-industrial-architecture-implementation.md`, then update verification results.

## DS architecture hardening handoff (2026-07-12)

- Status: local hardening changes prepared for push; see `docs/CODEX_HANDOFF.md` for the authoritative next-task list.
- Verified before final documentation-only edits: `102 passed`; `ruff check .`; `mypy app config`; `frontend/npm run typecheck`; `frontend/npm run test`.
- This handoff intentionally does not claim a finished React/Tauri product, real task dispatch, SSO, production worker, or production storage adapters.
- The user requested no further tests after the verification listed above. Next Codex must re-run the verification suite before extending or merging these changes.

## 审核工作台 API（2026-07-13）

- 状态：第一阶段已完成并已验证；React 审核界面尚未开始。
- 分支：`modular-architecture`。
- 已完成：
  - `GET /api/v1/forms/{form_id}`：返回表单摘要、字段坐标、当前值、识别候选、当前记录和受控证据 URL。
  - `GET /api/v1/forms/{form_id}/evidence/{file_id}`：按表单归属与图片/音频权限读取证据；DTO 不返回本地 `uri` 或绝对路径。
  - `GET /api/v1/forms/{form_id}/review-history`：返回版本与审计元数据。
  - 审核租约新增 heartbeat、本人释放和管理员强制释放接口。
  - `QueryForms.workbench()` 作为工作台读模型；路由只消费 DTO，不直接读取 SQLAlchemy Row。
- 验证结果：`107 passed`；`uv run python -m ruff check .` 通过；`uv run python -m mypy app config` 检查 111 个源文件通过。
- 未完成：规则结果、队列/分类/模板/主数据/导出 API；真实任务 Handler；React/Vite 审核工作台；Tauri 壳；生产认证与存储/Worker。
- 下一位操作：以 `docs/design/review-workbench-style.md` 为唯一视觉基线，在 `frontend/` 创建 React/Vite 应用；只通过 API Client 与 Shell Ports 调用后端和 Web/Desktop 能力，不直接访问数据库、本地证据路径或 Tauri API。

## React Web 审核工作台（2026-07-13）

- 状态：Web Shell 第一阶段已完成并已验证；桌面 Tauri 壳尚未开始。
- 分支：`modular-architecture`。
- 已完成：
  - 新增 `frontend/apps/web` 的 React + TypeScript + Vite 应用，并保留 Web/Tauri 共享 Feature 的边界。
  - 审核台遵循 `docs/design/review-workbench-style.md`：深海蓝导航、左图右表、字段与图片框联动、低置信度异常优先、底部详情抽屉。
  - `@form-detection/api-client` 新增审核工作台 DTO 与 API Client；浏览器 `fetch` 使用无绑定调用，避免原生 `fetch` 的 `Illegal invocation`。
  - 审核锁获取/续租/释放和确认请求均经 API Client；Web 通知只经 Shell Port 调用。
  - 本地浏览器验收：加载隔离演示表单、显示原图与 4 个字段框、编辑表格、低置信候选、获取与释放审核锁。
- 验证结果：前端根 `npm run test`（TypeScript + Vitest 3 项）通过；`npm run build:web`（Vite 生产构建）通过。
- 未完成：真实队列/规则/统计图表、草稿保存、退回/作废、任务进度、模板与主数据页面、Tauri v2 壳，以及生产认证。
- 下一位操作：先补齐工作台规则/队列 API，再在 `frontend/features/review-workbench` 抽取可复用组件；不得让 React 状态替代审核事实、审计事件或租约。

## 模板驱动纸质表单闭环：Phase A（2026-07-13）

- 状态：进行中；模板身份、版本、打印与 Web 设计器已完成，真实图片导入/识别/审核队列/导出仍未完成。
- 已完成并推送至 `modular-architecture`：
  - 模板版本、字段、打印产物三张独立表与 Alembic `002` 迁移；不改写历史 `forms` 数据。
  - `IFD|template_key|version|checksum` 模板二维码、可选 `SHEET|batch|sequence|checksum` 纸张实例码、A4/A5 标准画布和 10/11/12/13 四角标记。
  - 草稿—预检—发布—克隆生命周期；字段不能覆盖模板二维码安全区，发布后不可改写。
  - 300 DPI PNG/PDF 打印产物及受控下载 API；响应不返回内部 URI 或绝对路径。
  - 模板 API 与 React Template Studio；审核工作台侧栏“模板与字段”已不再是死按钮。
  - 企业历史工资表已映射为四类种子模板，见 `docs/design/legacy-payroll-template-inventory.md`；原文件未改写。
- 本阶段验证：模板领域/仓储/迁移/预检/渲染/API 定向测试通过；前端 `npm run test`、`npm run build:web` 通过。
- 明确未完成：受控图片上传、FORM_IMPORT Handler、QR 解码与人工分类回退、ArUco 透视校正、RecognitionAttempt、自动预填、真实审核队列/草稿/退回/作废、模板化 XLSX 导出、ZIP 模板包导入及 Tauri 壳。
- 下一位操作：实现白名单 `FORM_IMPORT` Handler 与 `/api/v1/imports`，上传只接受受控二进制内容和 `Idempotency-Key`，不得接受客户端本地路径或任意任务 operation。

## React 工作台交互修复：真实队列（2026-07-13）

- 状态：已完成并在本地服务验证；本节只解决侧栏“看得到、点不动”的队列缺口，不代表主数据编辑或草稿流程完成。
- 已完成：
  - `GET /api/v1/forms/queue/{classification|review|exceptions|exportable}` 返回真实表单摘要和真实计数；查询不再依赖 `RecordVersion`，因此刚导入、尚未首次确认的表单也会出现在队列中。
  - React 侧栏四个队列均可切换，主区域显示队列表单卡片并可打开审核工作台；图片导入、加载和确认后会刷新计数。
  - “数据管理”直接触发受控图片导入；“员工/工单”和“产品/工序”不再无响应，改为明确说明主数据持久化与编辑 API 尚未实现的页面。
- 本地验证：后端 `GET /health/ready`、`GET /api/v1/forms/queue/review` 返回 200；前端 `npm run typecheck` 通过；浏览器已确认四个真实计数和主数据入口页面可见。
- 明确未完成：主数据 SQLite 迁移与 CRUD、保存草稿、退回/作废、确认并领取下一张的原子 API、规则异常真实规则来源、导出中心与 Tauri 壳。不要将前端的“当前没有表单”误解为队列功能未接通——它表示本地数据库当前没有匹配状态的数据。
- 下一位操作：优先实现主数据的持久化模型、权限 API 与编辑页；随后实现草稿和 `confirm-and-claim-next` 事务，再把规则与导出状态接入队列。

## 模板中心可视化设计器：Task 1（2026-07-13）

- 状态：已完成并通过需求符合性与代码质量两轮审查。
- 已完成：`TemplateVersion` 新增草稿字段替换与删除；替换必须保留字段键和页面规格，未知字段明确失败；所有已发布/停用/退役版本继续不可变。
- 验证：`uv run pytest tests/unit/test_templates_domain_ds.py -q`，`8 passed`；Ruff 与 mypy 定向检查通过。
- 提交：`0cf97fb`、`363a512`。
- 下一步：补齐模板库查询、草稿字段 mutation 用例和 API 契约，再连接 React 模板库与只读预览。

## 模板中心可视化设计器：Task 2（2026-07-13）

- 状态：已完成并通过需求符合性与代码质量两轮审查。
- 已完成：模板仓储支持去重、字典序模板键查询；`TemplateVersions` 支持完整版本列表及草稿字段替换/删除用例，顺序稳定为模板键、版本、版本 ID。
- 验证：仓储与用例定向测试 `7 passed`；审查记录显示全量测试 `139 passed`，另有 2 个未改动 identity 默认值既有失败；Ruff 与 mypy 通过。
- 提交：`1f46d23`。
- 下一步：公开受权限保护的模板库、版本读取、克隆与字段编辑 API，并补 HTTP 契约测试。

## 模板中心可视化设计器：Task 3（2026-07-13）

- 状态：已完成，需求审查与代码质量复审均通过。
- 已完成：模板库/版本详情/复制调优/草稿字段 PATCH 与 DELETE API；字段、页面、父版本、打印件元数据形成完整客户端契约，内部存储 URI 始终不返回。
- 安全与错误：读写权限分离；缺失模板为 `TEMPLATE_VERSION_NOT_FOUND`，缺失字段为 `FIELD_NOT_FOUND`，发布版修改为 `INVALID_LIFECYCLE`；POST/PATCH 的 OpenAPI 请求体已验证存在。
- 验证：模板 API 定向测试 `6 passed`，Ruff 与 mypy 定向通过。全量套件保留 2 个未改动 identity 默认值既有失败。
- 提交：`4b7ba00`、`30dd99c`、`498540b`。
- 下一步：扩展 TypeScript API Client 和纯画布几何模型，再实现模板库与只读预览页面。

## 模板中心可视化设计器：Task 4（2026-07-13）

- 状态：已完成并通过需求与代码质量复审。
- 已完成：前端模板 API Client 支持模板列表、详情、复制、字段更新/删除；完整 DTO 从公共包导出。画布几何模型会限制页面边界，并在二维码安全区冲突时精确保留原坐标。
- 兼容性：默认浏览器 `fetch` 采用无绑定调用，避免 `Illegal invocation`；草稿、预检失败与待发布版本均允许继续调优，终态版本保持只读。
- 验证：前端定向测试 `11 passed`，`npm run typecheck` 通过。
- 提交：`33afddb`、`a8a07f2`、`569ccb4`。
- 下一步：实现模板库首屏和发布版本只读预览，用户点击“基于此模板调优”后才创建可编辑草稿。

## 模板中心可视化设计器：Task 5（2026-07-13）

- 状态：已完成，需求审查及多轮代码质量复审均通过。
- 已完成：模板中心首先进入真实模板库；支持搜索、状态筛选、诚实空状态、空白草稿；发布版本只读预览字段与打印件，点击“基于此模板调优”后才克隆草稿。
- 草稿连续性：模板库 API 同时返回发布版本与活动草稿，预检失败/待发布草稿均可恢复；保留字段添加、预检和发布的可工作编辑流程。
- 可靠性：处理复制请求导航竞态、失败重试与无障碍错误提示；模板库、预览和编辑器均增加桌面/平板/手机断点。
- 验证：模板 API 测试 `7 passed`；前端定向测试 `10 passed`；前端类型检查与生产构建通过。
- 提交：`fb99363`、`556e67f`、`2207158`。
- 下一步：将当前表单配置编辑升级为真正的画布字段选择、拖动/缩放和右侧属性检查器。

## 跨账户队友交接（2026-07-13）

- 当前远程分支 `modular-architecture` 已完成模板中心计划 Task 1–5；Task 6 在开始后按用户要求停止，未留下未提交文件。
- 永久交接文档已更新为 `docs/CODEX_HANDOFF.md`，包含完成清单、未完成清单、队友执行顺序、验收门槛、真实样本方案和本地运行命令。
- 下一位 Codex 必须先完成可视化画布编辑器，再做四个通用模板的幂等 seed；模板库不得在前端伪造不存在的发布模板。
- 当前验证边界仍是定向模板/API/前端验证；全量 Python 套件存在 2 个 identity 默认值既有失败，必须在正式验收中处理或明确说明。

## 全量质量门复测与身份默认值修复（2026-07-14）

- 对照交接报告重新执行 Python、Ruff、mypy、前端测试和生产构建。
- 确认原报告记录的 2 个 identity 失败仍存在：内置身份错误地默认使用
  `local-admin/ADMIN`，违反最小权限设计。
- 恢复内置回退身份为 `local-operator/OPERATOR`；需要更高权限的本地 Demo 必须通过
  环境配置显式授予。
- 同时修复报告未记录的 2 个 Ruff 行长度错误。
- 最终验证：Python `147 passed`；Ruff 全部通过；mypy 检查 120 个源文件无问题；
  前端 5 个测试文件共 `18 passed`；Web 生产构建通过。

## 模板中心可视化设计器：Task 6/7（2026-07-15）

- 状态：Task 6 实现完成并提交；Task 7 本地验证和交接记录完成，远端推送待授权。
- 提交：`a8374b6`（可编辑模板草稿画布与字段检查器）。
- 已完成：
  - A4/A5 标准比例画布、字段图层选择和右侧属性检查器；
  - 指针拖动、右下角缩放、方向键移动与 `Alt+方向键` 调整大小；
  - pointer-up 后通过 `replaceField` 持久化，刷新并恢复草稿后坐标与属性不丢失；
  - QR、SHEET、四角定位标记和页面边缘保护，坐标输入使用相同拦截规则；
  - 显示名、数据/输入类型、识别引擎、阈值与标准坐标显式保存；
  - 删除确认、预检状态失效、通过后发布、发布终态只读以及PNG/PDF打印件入口；
  - 桌面、平板和375px移动端响应式布局。
- 浏览器验收：创建草稿→新增字段→修改并刷新持久化→拖动→保护区拒绝→键盘移动
  →预检→发布→只读→确认PNG/PDF打印件入口→克隆V2→确认删除；浏览器控制台无错误。
- 自动化验证：Python `147 passed`；Ruff 全部通过；mypy检查120个源文件无问题；
  前端5个测试文件共`19 passed`；TypeScript类型检查和Web生产构建通过。
- 明确未实现：ZIP模板包、多页模板、动态明细行和Tauri桌面壳。

## 四个企业模板幂等安装 seed（2026-07-15）

- 状态：实现、全量质量门与真实新数据库浏览器验收均已完成，待本地提交和远端推送。
- 新安装的 FastAPI/Streamlit 组合根会幂等写入 4 个 `PUBLISHED` V1 模板：
  `PAYROLL_HOURLY`、`PAYROLL_STANDARD_PIECE`、
  `PAYROLL_FIXED_PRODUCTION_GRID`、`PAYROLL_EQUIPMENT_PROCESS`。
- 每个模板包含公共字段、岗位专属字段、固定 `line_01`–`line_10`、归一化坐标、
  识别策略、必填/范围/枚举规则及稳定 `workbook/worksheet/business_column` 导出目标；
  不含历史姓名、工资或业务记录。
- 首次安装生成 PNG/PDF；重复安装保持版本和完整产物不变，缺失/损坏的基础打印产物会修复；
  相同 `template_key + version` 的不同内容会在写入任何其他 seed 前整体拒绝。
- 补齐字段规则/导出目标 API 持久化及设计器属性编辑；后端发布预检现在同步阻止
  SHEET、四角 ArUco 和打印边缘冲突。模板 QR 向左调整，实测生成打印件可被 OpenCV 解码。
- 浏览器验收：全新数据库首次打开模板中心显示 4 个已发布模板；计时模板 V1 有 24 个字段、
  PNG/PDF 入口；克隆 V2 后规则与导出映射可见且可编辑；控制台无错误。
- 最终验证：Python `154 passed`；Ruff 全部通过；mypy 检查 121 个源文件无问题；
  前端 5 个测试文件共 `19 passed`；TypeScript 类型检查和 Web 生产构建通过。
- 下一步：审核工作台保存草稿、退回/作废、人工分类与原子 `confirm-and-claim-next`。

## 审核图像坐标系修复（2026-07-15）

- 使用 `dd8df17bbee1ec9f7ec467c12e10be09.png` 复现并确认：模板 QR 与 ArUco
  10/11/12/13 均成功识别，系统已生成标准 `CORRECTED_IMAGE` 和 24 个字段裁切；原问题
  不是四角定位失败，而是审核页将标准画布坐标覆盖到低分辨率 `ORIGINAL_IMAGE`。
- 审核页现在优先显示 `CORRECTED_IMAGE` 并叠加字段框；只有原图时会隐藏标准坐标框并显示
  明确的未校正提示，避免误导审核人员。
- 工作台 API 公开字段的 `recognition_engine`；前端会明确标识 `manual` 字段为人工录入。
  当前项目和本机均没有中文 OCR 引擎，因此日期、班次和姓名不会伪造自动识别结果。
- 验证：Python 全量 `154 passed`；Ruff 全部通过；mypy 检查 121 个源文件无问题；
  前端 5 个测试文件共 `21 passed`；TypeScript 类型检查和 Web 生产构建通过。

## 审核工作台事务闭环（2026-07-15）

- 新增持久化审核草稿：保存和重载不会创建正式 `RecordVersion`，草稿写入独立审计；
  同一审核人刷新页面后可原子恢复并续期尚未过期的 Lease，其他审核人仍收到 409。
- 退回要求原因、版本和 Lease，原子清除草稿/Lease 并进入 `RECAPTURE_REQUIRED`；
  作废追加不可变 `VOIDED` 版本，保留原因、证据和审计。
- `confirm-and-claim-next` 在同一事务中校验权限、Lease、乐观版本和模板规则，写确认版本，
  释放当前 Lease，并按 `priority DESC, created_at ASC, form_id ASC` 跳过被占用表单领取下一张。
- 人工分类页面只展示 `PUBLISHED` 模板；分类结果写审计并幂等创建持久化
  `FORM_RECOGNITION` 任务。任务 Handler/生产 Worker 仍属于后续阶段。
- 新增 Alembic `003`：审核草稿表、表单优先级和队列排序索引；旧版自动建库会先兼容补列，
  再补建新表和索引，不丢失原有数据。
- 浏览器自验覆盖：草稿保存/刷新恢复、租约恢复、退回、作废、确认并领取下一张、人工分类；
  数据库复核确认状态、版本、审计与 `PENDING` 识别任务，页面控制台无错误。
- 最终质量门：Python `163 passed`；Ruff 全部通过；mypy 检查 121 个源文件无问题；
  前端 5 个测试文件共 `22 passed`；TypeScript 类型检查和 Web 生产构建通过。
- 下一步：主数据 CRUD；本阶段按用户要求完成后暂停，不进入下一阶段。

## 模板库名称、草稿放弃与退役生命周期（2026-07-15）

- 新增独立 `template_metadata` 与 Alembic `004`：模板键继续作为不可变技术标识，中文名称和
  用途说明可在创建时填写，也可在模板库或编辑器中随时修改；旧数据库会无损回填内置模板名称。
- 草稿、预检失败和待发布版本支持“放弃草稿”，删除当前未发布版本及其字段；仅有该草稿的
  模板族会同步从模板库消失。发布版本拒绝物理删除。
- 已发布模板支持“退役模板”：有活动草稿时要求先明确放弃，退役后不再进入人工分类候选，
  但历史版本、字段、二维码解析依据和 PNG/PDF 打印产物全部保留并可只读预览。
- 内置 seed 的内容冲突指纹不再把生命周期状态当作模板内容；人为退役内置模板后重启不会被
  自动重新发布，真实字段内容冲突仍会整体拒绝。
- 同步修复审核字段状态：低置信度候选被人工填写非空值后显示“已就绪”；可选数字字段留空
  不再触发数值规则阻断，数值 `0` 被正确视为有效值。
- 验证：Python 全量 `168 passed`；Ruff 与 mypy 通过；前端 5 个测试文件 `26 passed`；
  TypeScript 类型检查和 Web 生产构建通过。由于本机 `.env` 显式使用 ADMIN，全量默认身份
  测试通过单次进程覆盖恢复 `local-operator/OPERATOR` 后执行，本机实际管理员配置未改变。

## 审核工作台模板规则即时校验（2026-07-15）

- 工作台 API 现在随字段返回显示名、数据类型以及必填、数值上下限和枚举允许值，前端“已就绪”与后端确认规则使用同一份模板定义。
- 枚举字段改为下拉选择；无效的历史草稿值、必填缺失、数值格式或范围错误会在对应行标红并显示具体原因，全部处理前禁用“确认并下一张”。
- `REVIEW_RULE_BLOCKED` 不再丢弃后端 `failures`，后端发现的字段级拦截会回填到电子表格对应字段，而不是只显示笼统提示。
- 当前本地待复核表单的 `shift` 和 `assessment_result` 草稿值均为不合法的 `"1"`；更新后需分别从模板允许值中重新选择。
- 验证：Python 全量 `169 passed`；Ruff 全部通过；mypy 检查 121 个源文件无问题；前端 5 个测试文件 `30 passed`；TypeScript 类型检查和 Web 生产构建通过。

## 重复图片与本地测试表单管理（2026-07-15）

- 图片导入现在在创建任务前按 SHA-256 查重；重复时返回已有表单编号、审核状态和允许操作，不再生成 `FAILED` 导入任务。
- 前端显示“打开已有表单”；退回表单明确要求上传内容不同的新采集图片；已作废表单在开发环境且操作者具有管理员权限时可“重新用于本地测试”。
- 重新测试沿用同一表单和不可变原始证据，保留作废版本并追加 `REOPEN_FOR_LOCAL_TEST` 审计事件；未知模板回到待分类，已有模板回到待复核。
- 开发环境管理员可在二次确认后彻底清除一张测试表单、关联任务、租约、草稿、版本、识别结果、审计和证据文件；生产环境接口返回 404，非管理员无权使用。
- 验证：Python 全量 `172 passed`；Ruff 全部通过；mypy 检查 121 个源文件无问题；前端 5 个测试文件 `30 passed`；TypeScript 类型检查及 Web 生产构建通过。

## 派生证据去重与导入失败回滚修复（2026-07-15）

- 根因：`evidence_files.sha256` 的全局唯一约束错误覆盖了 `CORRECTED_IMAGE` 和 `FIELD_CROP`；不同表单的空白裁切内容相同时，字段行已提交而证据写入冲突，任务停在 60% `RUNNING` 并留下半成品。
- Alembic `005` 将普通 SHA 索引与仅限 `ORIGINAL_IMAGE` 的部分唯一索引分离；原始图片继续全局去重，派生证据允许相同内容，并兼容匿名唯一约束和命名唯一索引两种历史数据库结构。
- 校正图和字段裁切写库失败时立即删除刚生成的孤立文件；其余处理异常会将任务标记为 `FAILED`，删除本次半成品表单、字段、证据及审计，但保留失败任务用于诊断。
- 当前本地库属于自动建表模式，已通过兼容升级逻辑应用相同索引，并修复 `FORM-f8a3bc1387fdfff1d10e17ef`：保留原图后清除半成品和孤立裁切，再次导入成功，任务 `SUCCEEDED`，标准计件模板 V1 字段数 `20/20`。
- 验证：Python 全量 `174 passed`；Ruff 全部通过；mypy 检查 121 个源文件无问题；前端 5 个测试文件 `30 passed`；TypeScript 类型检查通过。

## 主数据 CRUD 与审核联动（2026-07-15）

- 新增 Alembic `006`、`master_data_records` 和 `master_data_audits`，统一持久化员工、工单、产品和工序；编码创建后不可修改，不提供物理删除。
- 管理员可创建、编辑、停用和恢复；业务角色拥有读取权限。更新和生命周期操作使用修订号/`If-Match` 乐观锁，冲突返回当前与提交版本。
- 每次创建、更新、停用和恢复均保存操作者、原因、时间及前后快照；停用记录默认不进入列表和审核字段选项，但可显式查询并恢复。
- React 主数据中心已替换占位页，支持四目录、搜索、显示停用项、JSON 扩展属性、版本编辑、停用/恢复和审计轨迹。
- 模板 `master_data_source` 已接入工作台下拉项；前端即时提示无效编码，后端确认时再次阻止未知或停用主数据。
- 浏览器自验中额外发现并修复全局 `fetch` 的调用绑定问题；最终完成员工 v1 创建、v2 更新、v3 停用、停用项筛选和 v4 恢复，审计 4 条且控制台无错误。
- 最终验证：Python 全量 `183 passed`；Ruff 全部通过；mypy 检查 122 个源文件无问题；前端 6 个测试文件 `34 passed`；TypeScript 类型检查和 Web 生产构建通过。
- 下一步：模板化导出中心与重导闭环。
