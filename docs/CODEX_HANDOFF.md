# Codex 协作交接与下一步实施清单

最后更新：2026-07-12  
工作分支：`modular-architecture`  
远程仓库：`git@github.com:lhh666-6/auto-decte.git`

## 产品目标与不可改变的原则

这是 Windows 本地优先的工业表单采集系统。稳定业务闭环已经存在：图片/音频证据、SHA-256 去重、人工确认和更正、版本与审计、识别候选、规则校验、查询追溯、XLSX 导出，以及默认关闭的 AI 和本地相似检索。

后续架构必须是**模块化单体的增量演进**，不得重写稳定链路。当前 SQLite、本地文件和进程内任务是唯一事实源；未来 PostgreSQL、NAS/S3、Worker 队列和 Qdrant 只能通过 Port/Adapter 替换。

## 目标界面与前端边界

最终前端是 React Feature Modules，由 Web Shell 和 Tauri Desktop Shell 承载并共享业务 Feature。业务状态不能分别存放在 React、Streamlit 或桌面壳中。

已确认的审核工作台视觉基线见 [review-workbench-style.md](design/review-workbench-style.md)，React 实现不得偏离其“左图右表、异常优先、证据—字段联动”的核心规则。

首个要真正实现的 Feature 是“人工审核工作台”：

- 左侧：原始图片、缩放/旋转、字段坐标框、字段裁切预览；
- 右侧：可编辑电子表格、字段分类、规则错误和 OCR/OMR 候选；
- 下方：审核锁、版本历史、审计事件、任务进度和关联统计；
- 字段、图片区域、电子表格和图表必须联动；
- Web 使用浏览器 File/Camera/Audio 能力，Desktop 通过 Tauri IPC 实现相同 Shell Port。

目前 `frontend/` 仅包含 Shell Port、API Client 类型和 Feature README；**没有 React 应用、没有 Tauri Rust 工程，Desktop Port 也是 stub**。不要把它报告为已完成的 React/Tauri 产品界面。

## 当前已完成并已验证的能力

Python 验证基线当前达到 102 项测试通过，Ruff 与 mypy 均通过；前端 TypeScript 的 `npm run typecheck` 与 `npm run test` 也通过。模块化分支已经具备：

- SQLite WAL、外键、忙等待；
- 本地身份/角色/权限模型；
- ReviewLease、审核版本冲突和 UnitOfWork；
- 持久化 Task、事件、幂等、重试、恢复和进程内 Runner；
- FastAPI、Problem Details、请求 ID、健康检查、审核与任务 API；
- Alembic 基线、备份/完整性组件、可观测性组件和前端契约骨架。

本轮本地收口的高风险修复：

- 恢复稳定的 `app.api.main:create_app` 兼容入口；
- 增加任务状态 URL；
- Alembic 支持显式数据库路径，生产模式验证 revision 而非自动建表；
- 备份恢复到独立 staging 目录，并校验 hash；
- 完整性检查增加无效版本指针、过期租约、孤立裁切；
- 默认不信任 `X-Roles` 请求头，测试才显式开启；
- 任务事件分配与写入在同一临界区，审核锁使用 SQLite 条件 upsert；
- SSE 使用持续轮询流、终态关闭和无缓存响应头。

## 队友 Codex 的任务清单

按以下顺序实施。每项完成后更新 `PROGRESS.md` 和本文件，提交前运行测试。

### A. 当前修复的验证与提交

```powershell
uv run python -m pytest -q
uv run python -m ruff check .
uv run python -m mypy app config
uv run python -c "from app.api.main import create_app; print(create_app().openapi()['openapi'])"
```

修复失败后提交“DS 架构收口”改动。不得混入 `data/`、`.runtime/`、缓存、真实证据或导出文件。

### B. 任务 API 与 SSE 的真实业务接入

当前 `POST /api/v1/tasks` 可以创建任务、状态 URL 可查询、SSE 可续传，但还未把业务操作映射到真实导入/识别/导出 Handler。

- 建立受限 `TaskHandlerRegistry`，只允许白名单 operation；
- 将导入、识别、导出入口改为创建持久化任务并注册真实 Handler；
- 执行中用 `TaskContext.report()` 写进度，取消时安全退出；
- 增加状态、取消、重试、失败详情测试；
- 不能把客户端传入的任意 operation 或本地路径直接交给 Runner。

### C. 审核工作台所需 API

补齐 React 审核工作台接口：

- `GET /api/v1/forms/{form_id}`：表单详情、版本、字段、规则结果；
- 基于 `file_id` 的受控证据读取 URL，绝不泄露本机绝对路径；
- 字段裁切/识别候选、审核历史、租约 heartbeat/release/force-release；
- 查询、导出、模板、主数据 API；
- DTO 不能返回 SQLAlchemy Row、Repository 或服务器文件路径；
- 写入接口统一支持权限、`Idempotency-Key` 和版本前置条件。

### D. 迁移、备份和恢复演练

- 生产配置必须 `auto_create_schema=false`；
- RestorePlan 始终先恢复到 staging，完整性通过后才允许人工切换；
- 备份 manifest 只保存相对路径和哈希；
- 补无效 Export 关联、孤立字段、任务恢复状态、manifest 自检；
- 文档中提到的 `/api/v1/admin/backup` 尚无路由，未实现前必须标为计划项。

### E. 可观测性与权限

- 将 `JsonLogFormatter` 接入 FastAPI 中间件、任务 Runner 和业务 Facade；
- 日志固定带 request ID、actor、module、operation、form/task ID、耗时和错误码；
- 实现敏感字段掩码，不记录原图路径、凭据、表单值或录音内容；
- `LocalErrorTracker` 通过 ErrorTracker Port 注入，保留 Sentry/OpenTelemetry 替换点；
- `allow_header_identity` 只用于测试/本地演示；生产替换为可信认证 Adapter。

### F. React / Tauri 实施

- 修复 `frontend` 工具链：根 `npm test` 当前指向未安装的 Jest；改为可重复 workspace 测试并提交 lockfile；
- 建立 React + TypeScript + Vite Web App，先做审核工作台与任务队列；
- 增加 Tauri v2 工程，但 Feature 只能调用 `shell-ports`，不能直接 import Tauri API；
- 为 Web/Desktop 的 File/Camera/Scanner/Audio/Notification Port 写行为测试；
- Streamlit 保留为诊断/过渡界面，改为显式导航，避免 `app/ui/pages/` 自动发现空白页。

## 风险与协作注意事项

- `_ds` 是 DS 贡献标识，不应成为外部部署契约。公共入口保持稳定名称，例如 `app.api.main`；不要让 README、uvicorn 命令或第三方集成依赖作者后缀。
- 审核锁与事件序列在本地并发已加强；未来多进程/多机器时使用数据库条件写入、PostgreSQL 事务或队列协调，不能依赖 Python 进程内锁。
- AI、向量、音频转写保持可选；关闭它们时核心导入、审核、查询与导出必须可用。
- 真实样表、员工数据、音频、SQLite 数据库、导出文件、密钥和 `.env` 绝不提交 Git。
- 不使用 `git reset --hard` 或 `git checkout --` 覆盖他人改动；拉取前先 `git status`，保持小而清晰的提交。

## 推荐协作流程

```powershell
git fetch origin
git switch modular-architecture
git pull --ff-only origin modular-architecture
uv sync --extra dev
uv run python -m pytest -q
```

每个任务使用独立分支，例如 `feature/task-handler-registry`、`feature/review-workbench-api`、`feature/react-review-workbench`、`feature/tauri-shell`。提交说明必须写清实现内容、验证命令、测试结果、已知限制和下一位 Codex 的下一步；推送分支后用 PR 合并，不直接覆盖 `main`。

## 本次验证边界

- 已执行并通过：Python `pytest` 102 项、`ruff check .`、`mypy app config`；前端 `npm run typecheck` 与 `npm run test`。
- 本文件、README、进度记录和 Git 忽略规则之后仅为文档/协作整理；按当前用户要求，未再执行额外测试。
- 未完成而必须由下一位 Codex 验收：真实任务 Handler 入队、React 审核工作台、Tauri 应用、真实 SSO、生产 Worker、PostgreSQL/NAS/S3/Qdrant Adapter、真实样表准确率与性能基线。

## 2026-07-13：审核工作台 API 第一阶段

此阶段已在 `modular-architecture` 分支实现并验证，作为 React 审核页面的唯一数据入口：

- `GET /api/v1/forms/{form_id}` 返回表单、字段坐标、当前值、OCR/OMR 候选、当前记录和不含服务器路径的证据 URL；
- `GET /api/v1/forms/{form_id}/evidence/{file_id}` 依表单归属及图片/音频权限受控读取证据；
- `GET /api/v1/forms/{form_id}/review-history` 返回版本和审计事件；
- 租约现有 acquire/confirm 之外，新增 heartbeat、本人 release 与管理员 force-release。

最新验证：`107 passed`，Ruff 通过，mypy 检查 111 个源文件通过。未实现的规则结果、队列/分类/模板/主数据/导出 API 仍不得在前端伪称已完成。

下一步为 React/Vite 审核工作台。严格遵守 [审核工作台视觉规范](design/review-workbench-style.md)：左图右表、字段—坐标双向联动、异常优先；业务 Feature 只能使用 API Client 和 Shell Ports，不能读取本地文件路径、数据库或直接调用 Tauri API。

## 2026-07-13：React Web 审核工作台第一阶段

`frontend/apps/web` 已不再是 README 骨架，而是可运行的 React/Vite Web Shell：

- 左侧原图画布叠加字段框，右侧舒适密度的可编辑电子表格；点击字段或图片框会保持同一选中状态；
- 通过 `ReviewWorkbenchApi` 调用版本化 API，包含详情、历史、证据、审核租约与确认；
- Web 通知经 `@form-detection/shell-ports` 处理；没有 Feature 直接读取数据库、本地证据路径或 Tauri API；
- 根 `npm run test`（TypeScript + Vitest 3 项）和 `npm run build:web` 均已通过，并在本地浏览器用隔离演示数据完成了加载、字段框、异常状态和审核锁的可视化验收。

仍未完成：真实队列/规则/统计图表、草稿与退回/作废、任务进度、模板/主数据页面、Tauri v2 壳和生产认证。下一阶段应先补相关 API，再把当前 Web Shell 的审核组件抽到 `frontend/features/review-workbench/`，保持 Web 与 Desktop 可共用。
