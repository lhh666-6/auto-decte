# 工业纸质表单系统技术基线与 PWA 改造评估

> 基线日期：2026-07-21
> 基线提交：`574dea0`（分支 `codex/low-token-ui-v2`）
> 判断原则：本文件以当前代码、锁文件、迁移和测试为准；旧计划或说明与代码不一致时，以代码为准。
> 检查边界：未读取运行数据库、真实上传图片、业务 Excel 内容、密钥，也未读取 `node_modules`、`dist`、`build` 或缓存目录。

## 状态定义

| 标记 | 含义 |
|---|---|
| **已实现** | 存在真实代码路径并已接入当前主流程或 API。 |
| **部分实现** | 核心结构存在，但能力、覆盖范围或生产可用性不完整。 |
| **接口/占位** | 只有类型、端口、任务记录或适配器骨架，当前流程没有真正执行。 |
| **未实现** | 当前仓库没有对应产品能力。 |

## 2026-07-21 PWA 移动端增量基线

本节覆盖并取代本文后续章节中“PWA、移动登录、IndexedDB 和移动提交未实现”的旧判断；桌面端本地完整权限模式仍保持原样。

- **移动身份：已实现**。员工主数据上的移动凭据使用 scrypt 加盐摘要，失败次数、锁定、授权配置和会话均持久化；浏览器使用 HttpOnly SameSite Cookie，写请求使用 CSRF Cookie/Header 双提交，不返回或保存 Bearer token。
- **移动定义和上下文：已实现基础**。页面只读取授权且已发布的电子 Definition；生产上下文、工单、产品和班组成员来自服务端主数据。竹丝笼 provider 未接入时明确 503，不生成演示资源。
- **电子提交：已实现基础闭环**。服务端校验 actor/subject、SELF/TEAM_LEADER_BATCH、同班组、Definition 版本、字段白名单和幂等键；Form、Field、Audit、Receipt、FactRecord 在同一事务内提交或回滚，并进入现有 NEEDS_REVIEW 工作台。
- **离线与同步：已实现**。IndexedDB 按 owner/device/localDraftId 隔离草稿，outbox 保留幂等键；401 暂停，403/409/422 最终失败，网络和 5xx 退避，成功回执后清理 outbox 和来源草稿。
- **PWA：已实现基础**。Manifest、图标、生成式 Service Worker、更新提示和公共设备退出清理已接线。所有 API、证据和下载路径均 NetworkOnly；未提交 outbox 存在时禁止立即激活更新。
- **仍非生产部署完成**。缺少真机证据、可信 HTTPS/反向代理、竹丝笼生产 provider、多人容量/故障演练和现场业务签字。

# 1. 项目概述

当前系统用于把工业现场的纸质工资/产量表单转成可追溯的电子记录：先设计并发布带二维码和定位标记的纸质模板，打印后由工人填写，再导入照片，经过模板识别、透视校正、字段裁切、有限的数字/勾选识别和人工审核，最终导出 XLSX。（代码：`app/domain/templates_ds.py`、`app/application/recognize_forms.py`、`app/modules/review/facade_ds.py`、`app/application/export_forms.py`）

- **主要用户**：当前实际界面面向本地操作员、审核员和财务导出人员；代码中还定义管理员和审计员角色，但默认没有登录界面。（代码：`frontend/apps/web/src/app/AppShell.tsx`、`app/modules/identity_access/models_ds.py`）
- **核心流程**：模板设计/发布 → 纸张打印 → 图片导入 → 自动或人工确认模板 → 图像校正/裁片 → 数字或 OMR 候选 → 人工审核 → 版本化确认/更正 → 导出预览 → XLSX 批次/重导。
- **部署形态**：**已实现，本地单机**。FastAPI 默认监听 `127.0.0.1:8000`，数据存放在本地 `data/`，前端由 Vite 独立启动。没有生产级多机部署配置。（代码：`config/settings.py`、`frontend/apps/web/vite.config.ts`）
- **纸质 OCR 流程**：**部分实现**。二维码、ArUco 定位、透视校正、裁片、单格数字模板识别和 OMR 已实现；通用手写数字串、中文文字和签名 OCR 未实现。（代码：`app/adapters/recognition/opencv.py`、`app/adapters/recognition/digits.py`、`app/application/recognize_forms.py`）
- **电子审核与导出**：**已实现基础闭环**。有队列、左图右表、字段候选、规则拦截、草稿、审核锁、确认/更正/退回/作废、审计、导出预览、批次和重导。（代码：`frontend/apps/web/src/workbench/ReviewWorkbenchPage.tsx`、`app/api/routers/review_ds.py`、`app/api/routers/exports_ds.py`）
- **成熟度**：可运行、测试覆盖较强的本地演示/技术基线，尚不是可供约 500 人、多设备、离线移动端使用的生产系统。主要缺口是身份认证、通用 OCR、独立任务 Worker、外部文件存储、PWA 离线提交与生产部署。

# 2. 仓库目录结构

| 目录 | 职责 |
|---|---|
| `frontend/apps/web/src/` | React 页面、路由、模板设计器、审核、基础数据、导出与样式。 |
| `frontend/packages/api-client/` | 手写 TypeScript API 客户端和 DTO；OpenAPI 生成文件仍为占位。 |
| `frontend/packages/shell-ports/` | 文件、相机、扫描、音频、通知的 Web 端口及 Tauri 占位。 |
| `app/api/` | FastAPI 工厂、路由、请求/响应模型、错误和请求编号中间件。 |
| `app/application/` | 导入、识别、模板版本、审核、查询、导出、AI 建议等应用服务。 |
| `app/domain/` | 表单、证据、记录版本、模板、字段规则等领域对象。 |
| `app/modules/` | identity、master_data、review、reporting、tasks、templates 等模块边界和 facade。 |
| `app/adapters/database/` | SQLAlchemy 表模型及 SQLite 仓储实现。 |
| `app/adapters/recognition/` | OpenCV 图像处理、数字模板和 OMR。 |
| `app/adapters/templates/` | 模板 PDF/PNG、二维码、ArUco 和拼版渲染。 |
| `app/adapters/export/` | openpyxl XLSX 输出及固定模板写入。 |
| `app/adapters/storage/` | 本地不可变证据文件存储。 |
| `app/adapters/ai/` | DeepSeek 最小客户端、结构化输出约束和禁用适配器。 |
| `app/infrastructure/` | SQLite 引擎、迁移、备份/完整性、任务存储及未接入的线程任务运行器。 |
| `app/ui/` | 旧 Streamlit 辅助页面；不是当前 React 主入口。 |
| `alembic/versions/` | 001—014 数据库迁移。 |
| `app/modules/reporting/assets/` | 代码内置、受 SHA-256 约束的固定 XLSX 报表资产。 |
| `tests/` | 单元、API、应用、适配器、集成、模块、架构和工具测试。 |
| `config/` | Pydantic Settings 配置。 |
| `docs/` | 当前状态、决策、任务和技术文档。 |

没有 Docker、Tauri 工程或生产部署目录；PWA Manifest、图标和 Service Worker 已存在。

# 3. 技术栈和版本

版本来自 `pyproject.toml`、`uv.lock`、`frontend/package.json`、`frontend/package-lock.json` 和本次本地环境核对。

| 类别 | 当前版本/结论 |
|---|---|
| Python | `3.11.*`；项目约束 `>=3.11,<3.12`，本地为 3.11.9。 |
| FastAPI / Uvicorn | FastAPI 0.139.0，Uvicorn 0.51.0。 |
| 数据/验证 | Pydantic 2.13.4，pydantic-settings 2.14.2，NumPy 1.26.4。 |
| 数据库 | SQLite；SQLAlchemy 2.0.51；Alembic 1.18.5。没有 PostgreSQL 驱动。 |
| OCR/图像/二维码 | OpenCV headless 4.11.0.86；二维码和 ArUco 均使用 OpenCV。无 Tesseract、PaddleOCR、pyzbar、qrcode Python 包。 |
| Excel | openpyxl 3.1.5。 |
| React | React/React DOM 18.3.1，React Router DOM 6.28.0。 |
| TypeScript / 构建 | TypeScript 5.9.3，Vite 5.4.21，`@vitejs/plugin-react` 4.7.0。 |
| 状态管理 | 无独立状态库；使用 React hooks、本地组件状态和少量 `localStorage`。 |
| UI/图标 | 无组件库、无图标库；自有 React 组件、原生控件和单一主 CSS。 |
| 测试 | pytest 9.1.1；Vitest 2.1.9；Testing Library React 16.3.2。 |
| 代码质量 | Ruff 0.15.21，mypy 1.20.2，TypeScript `tsc`。 |
| Tauri | **接口/占位**：只有 `desktop_ds.ts` 抛错桩；无 Tauri 包、Rust 或配置。 |
| Docker | **未实现**。 |
| PWA 依赖 | **已实现基础**：Vite PWA/Workbox、Manifest、图标、`idb`、离线草稿和 outbox 已接线。 |

# 4. 当前启动方式

## 前端

在 `frontend/` 下：

```text
npm install
npm run dev:web
npm run build:web
```

`dev:web` 会先构建 `api-client` 和 `shell-ports`，然后启动 Vite；开发默认端口为 5173，端口占用时 Vite 可顺延。`/api` 默认代理到 `http://127.0.0.1:8000`，可通过 `VITE_API_TARGET` 调整。（代码：`frontend/package.json`、`frontend/apps/web/package.json`、`frontend/apps/web/vite.config.ts`）

## 后端

在仓库根目录：

```text
uv sync --extra dev
uv run python -m uvicorn app.api.main:create_app --factory --host 127.0.0.1 --port 8000
```

- 默认 Web 地址：`http://127.0.0.1:5173/`；API：`http://127.0.0.1:8000/`。
- 配置来源：默认值 + 根目录 `.env` + `FORM_DEMO_` 环境变量；前端另使用 Vite 环境变量。（代码：`config/settings.py`）
- 当前明确以 Windows 10/11 单机为目标；路径代码大多使用 `pathlib`，理论上可在 WSL/Linux 运行，但 CJK 字体、文件选择、打印和路径权限需重新验证。WSL 中的 `127.0.0.1`、浏览器与 Windows 文件路径也可能跨边界。
- **一条命令启动：未实现**。前后端需分别启动。
- **健康检查：已实现**：`GET /health/live` 与 `GET /health/ready`。ready 检查本地证据目录可创建并查询导出批次，但不检查 OCR、外部 AI 或磁盘余量。（代码：`app/api/routers/health_ds.py`）
- **HTTPS：未配置**。局域网/PWA 部署必须在反向代理或 Uvicorn 外层增加 TLS。

# 5. 前端现状

| 模块 | 状态 | 真实现状与代码位置 |
|---|---|---|
| 应用入口 | **已实现** | `frontend/apps/web/src/main.tsx` → `App.tsx` → `app/router.tsx`。 |
| 路由 | **已实现** | 审核分类/复核/重拍/表单详情、模板库/预览/草稿、4 类基础数据、导出；见 `app/router.tsx`。 |
| 顶部导航 | **已实现** | 审核工作台、模板中心、基础数据、导出数据；见 `app/AppShell.tsx`。 |
| 审核工作台 | **已实现** | 队列、选单、草稿、字段审核、快捷键、确认/更正/退回/作废、下一张；见 `workbench/ReviewWorkbenchPage.tsx`。 |
| 模板中心 | **已实现** | 模板库、搜索/筛选、空白创建、克隆、预览、草稿编辑、预检、发布、打印制品；见 `TemplateLibrary_ds.tsx`、`TemplateStudio_ds.tsx`、`TemplateCanvasEditor_ds.tsx`。 |
| 基础数据 | **已实现但范围有限** | 员工、工单、产品、工序 CRUD、停用/启用、审计；见 `MasterDataCenter_ds.tsx`。 |
| 导出数据 | **已实现** | 报表选择、过滤、预览、排除原因、任务轮询、批次下载/重导、只读助手；见 `ExportCenter_ds.tsx`。 |
| 图片上传 | **已实现** | 单张、拖放多张、选择多张、选择文件夹；见 `workbench/BatchImportPanel.tsx`。 |
| 图片预览 | **已实现** | 原图/校正图切换、缩放、旋转、拖动、字段框、字段裁片；见 `workbench/EvidenceViewer.tsx`。 |
| 左图右表 | **已实现** | 桌面端可拖动 35%—65% 分隔；见 `ReviewWorkbenchPage.tsx`、`styles.css`。 |
| 批量上传 | **已实现** | 浏览器逐文件调用导入 API，显示独立状态；不是服务器端压缩包批处理。 |
| 图片总览 | **已实现** | 缩略图墙和导入批次总览；见 `workbench/ImportOverview.tsx`。 |
| 响应式 | **部分实现** | 多个 960/820/560px 断点；审核在窄屏切换“图片/电子表格”，模板、基础数据、导出也有降栏。见 `styles.css`。 |
| 手机可用性 | **部分实现** | 页面能收窄使用，但无真机验收、触控专项、离线、安装或相机流程；复杂模板设计器不适合作为首批手机功能。 |
| 状态/错误 | **已实现基础** | 业务语言映射、ProblemDetails 展示、加载/空态/重试；无全局错误监控。见 `ui/business-errors.ts`、`ui/ProblemNotice.tsx`。 |
| API 客户端 | **已实现但手写** | `frontend/packages/api-client/src/*`；`generated_ds.ts` 仍是 OpenAPI 占位，存在前后端类型漂移风险。 |
| SSE/轮询/WebSocket | **部分实现** | 后端有 SSE 任务事件；当前界面主要用轮询识别/导出任务。无 WebSocket。（代码：`app/api/routers/tasks_ds.py`、`RecognitionProgress.tsx`、`exports_ds.ts`） |
| 未保存提醒 | **已实现** | `beforeunload` 和页面切换确认；草稿保存在后端，不是离线草稿。 |
| 审核锁 | **已实现** | 获取、120 秒心跳、释放；锁失效会结束本次审核。 |
| 组件/样式 | **部分实现** | 页面已拆为业务组件，但样式主要集中在 `styles.css`，缺少设计令牌组件库和移动端视觉回归。 |

状态主要保存在组件内，刷新后只有服务端草稿和桌面分栏比例能够恢复；没有 Redux/Zustand、IndexedDB 或全局提交队列。

# 6. 后端架构

- **入口**：`app/api/main.py:create_app` 读取 `Settings`、构建服务并调用 `app/api/main_ds.py:create_app`。
- **API 版本**：业务 API 统一以 `/api/v1` 开头；健康检查位于 `/health`。
- **模块边界**：API → application/module facade → domain/ports → adapters/infrastructure。它是同一进程中的模块化单体，不是微服务。（代码：`app/services/container.py`）
- **依赖注入**：启动时手工组装 `Services`，保存到 `app.state.services`，路由通过 FastAPI `Depends(get_services)` 取得；没有 DI 容器。
- **数据验证**：请求/响应使用 Pydantic；领域对象 `dataclass` 自校验；审核和导出另有确定性规则。（代码：`app/api/schemas/`、`app/application/template_versions_ds.py`、`app/modules/review/facade_ds.py`）
- **错误处理**：HTTP 与未捕获异常统一转换为 `application/problem+json` 并带请求编号；部分路由提供业务错误码。（代码：`app/api/main_ds.py`、`app/api/errors/problem_ds.py`）
- **后台任务**：导出使用 FastAPI `BackgroundTasks`，进程重启可从持久任务事件恢复部分状态；图片导入仍在请求内同步处理。`InProcessTaskRunner` 和 worker 数量配置存在但未接入主服务，属于**接口/占位**。（代码：`app/modules/reporting/handler_ds.py`、`app/infrastructure/tasks/in_process_ds.py`）
- **文件处理**：图片原始字节上传；路径由服务端生成并做根目录逃逸检查。模板制品和导出均保存在本地文件系统。
- **识别任务**：二维码自动分类时会立即执行校正/裁切/有限识别；人工分类只创建 `FORM_RECOGNITION` 任务记录，没有消费者执行，属于阻断性缺口。（代码：`app/api/routers/imports_ds.py`、`app/api/routers/classification_ds.py`）
- **导出任务**：有持久 task/event、后台执行、pending/final 两阶段、哈希校验和中断恢复。
- **审计**：模板分类、校正、裁片、确认/更正、锁、主数据、导出预览/批次等写审计或版本记录；不是统一覆盖每个 HTTP 请求的安全审计。
- **并发控制**：SQLite WAL + 5 秒 busy timeout；审核 lease；记录版本 `If-Match`；主数据 revision；任务幂等键。
- **审核锁**：数据库表持久化、TTL 默认 300 秒、原子抢占、同一操作者恢复、心跳和强制释放审计。（代码：`app/modules/review/lease_service_ds.py`、`app/modules/review/repository_ds.py`）
- **幂等保护**：导入、导出和通用任务采用 `(actor, operation, resource, idempotency_key)` 唯一约束并校验 payload hash；审核/主数据用乐观版本。并非所有 POST 都有幂等键。

# 7. 数据库结构

当前是 **SQLite**，默认文件 `data/database/demo.db`；SQLAlchemy 声明式映射直接访问，无独立 ORM `relationship()` 对象导航。（代码：`app/adapters/database/models.py`、`app/infrastructure/database/sqlite_ds.py`）

| 业务实体 | 表/状态 | 关系与实现状态 |
|---|---|---|
| 模板元数据 | `template_metadata` | `template_key` 字符串主键。 |
| 模板版本 | `template_versions` | 字符串 `version_id` 主键；`template_key + version` 唯一；状态和页面/静态元素/拼版 JSON。 |
| 模板字段/制品 | `template_fields`、`template_artifacts` | 外键到模板版本；字段定义 JSON；制品 URI 唯一。 |
| 岗位配置版本 | `job_profile_versions` | 外键绑定模板版本；固定选项、计价、扣减和导出映射均为 JSON。 |
| 表单实例 | `forms` | 字符串 `form_id` 主键；引用模板身份但数据库未声明到模板表的复合外键。 |
| 图片资产/证据版本 | `evidence_files` | 外键到表单；类型含原图、缩略图、校正图、裁片、音频；URI 唯一。原图 SHA 有 SQLite 部分唯一索引。 |
| 识别任务 | `tasks`/`task_events` | 通用持久任务；没有专门 recognition_jobs 表。 |
| 字段候选 | `recognition_attempts` | 外键到 `form_fields`，裁片文件 ID 外键到证据。 |
| 最终确认值/记录版本 | `record_versions` | 外键到表单；`form_id + version` 唯一；values JSON，previous_version 逻辑链。 |
| 当前字段值 | `form_fields` | 外键到表单；当前值、来源和版本，候选与裁片通过字段 ID 关联。 |
| 员工/工单/产品/工序 | `master_data_records` | 共享表，复合主键 `(catalog, code)`，业务属性 JSON；另有 `master_data_audits`。 |
| 班组 | 无独立表 | 仅作为员工 `team` 属性或表单值。 |
| 设备/供应商 | 无表 | **未实现**。 |
| 审核状态 | `forms.review_status` | 字符串枚举状态；不是独立表。 |
| 审核锁/草稿 | `review_leases`、`review_drafts` | 表单级独占锁与服务端草稿。 |
| 导出批次 | `export_batches` | 保存记录版本快照、映射快照、哈希、文件路径和 supersedes ID。 |
| 报表映射 | `report_definition_versions` | 报表定义/固定单元格和表格映射以 JSON 保存。 |
| 审计记录 | `audit_events`、`master_data_audits` | 表单审计与主数据审计分开。 |
| AI 建议 | `ai_reviews` | 可保存建议；当前主 API 未触发通用 AI 审核。 |

- **主键类型**：主要为业务前缀字符串；主数据为字符串复合主键；没有 UUID 数据库类型。
- **不可变策略**：已发布模板/岗位配置通过领域方法禁止修改；记录更正追加新 `record_versions`；证据标记不可变且不覆盖原文件。
- **停用策略**：模板/岗位配置/报表有 `RETIRED`，主数据有 `active=false`，表单有 `VOIDED`；没有通用 `deleted_at`。
- **迁移**：Alembic 001—011，当前头为 011；启动还包含旧库兼容补列和可选自动建表。（代码：`app/infrastructure/database/migrations.py`）
- **迁移 PostgreSQL 的触点**：数据库 URL和驱动、SQLite PRAGMA/WAL、`sqlite.dialects.insert` 的 lease upsert、SQLite 部分索引、JSON 行为、迁移兼容 SQL、并发/事务测试、备份工具、本地文件路径及单进程任务恢复都需调整。重点文件：`sqlite_ds.py`、`review/repository_ds.py`、`models.py`、`alembic/`、`backup/`、`services/container.py`。

# 8. 图片和文件存储

| 项目 | 状态与位置 |
|---|---|
| 原始图片 | **已实现**，`data/evidence/original-images/...`；实际相对 URI 入 `evidence_files`。 |
| 校正图片 | **已实现**，`corrected-images/`，PNG，永久证据。 |
| 缩略图 | **已实现**，`thumbnails/`，最长边约 360px、JPEG。 |
| 字段裁片 | **已实现且永久保存**，`field-crops/`，并关联识别候选。 |
| SHA-256 | **已实现**；文件入库记录哈希，原图全局去重，导出和模板制品也校验哈希。 |
| 重复图片 | 返回 409 和原表单引用；批次中记 `NEEDS_ACTION`；开发模式可清理测试表单。 |
| 导出文件 | `data/exports/`，记录绝对路径、SHA、版本快照；下载前再次校验。 |
| 模板文件 | 打印 PNG/PDF 在 `data/evidence/template-artifacts/<template>/`；固定 XLSX 资产在 `app/modules/reporting/assets/`。 |
| 外部存储 | NAS、MinIO、S3 **未实现**；只有 `LocalEvidenceStorage`。 |

文件路径从服务端生成，数据库只返回受控下载 URL，不向前端暴露真实根路径。（代码：`app/adapters/storage/local.py`、`app/api/routers/workbench_ds.py`、`app/api/routers/exports_ds.py`）

容量风险较高：每张表可能同时保留原图、缩略图、整页校正图和每字段 PNG 裁片；无配额、容量告警、生命周期或归档任务。只有失败事务和开发测试清理会删除文件。备份/完整性服务可复制 SQLite、证据和导出到备份目录并做哈希核对，但未形成定时运维入口。（代码：`app/infrastructure/backup/`、`app/tools/verify_integrity_ds.py`）

# 9. 模板系统

- **数据模型：已实现**。`TemplateVersion` 包含纸张、字段、规范化坐标、静态元素、打印拼版和状态；`JobProfileVersion` 复用核心布局并保存岗位差异。（代码：`app/domain/templates_ds.py`）
- **版本/不可变：已实现**。DRAFT → READY_TO_PUBLISH/PREFLIGHT_FAILED → PUBLISHED → RETIRED；已发布版本不能编辑，只能克隆新版本。
- **字段坐标：已实现**。以页面宽高 0—1 的规范化 `Rect` 保存，识别时换算为 canonical pixel。
- **二维码：已实现**。OpenCV 生成/读取模板身份二维码；支持模板+岗位版本和单张 sheet instance 双二维码。
- **定位标记：已实现**。四角 ArUco ID 10—13，透视校正依赖这些标记。
- **打印 PDF/PNG：已实现**。默认 300 DPI，可输出单页 PDF/PNG和拼版 PDF。（代码：`app/adapters/templates/print_renderer_ds.py`）
- **纸张/拼版：已实现**。模型支持 A4、A5 和 CUSTOM 宽高；存在 A5 两拼等配置，预检会检查是否放得下。
- **模板设计器：已实现基础**。空白创建、添加/复制/删除字段、拖放、缩放、网格/对齐、纸张设置、字段行为、预检/发布可用；复杂表格自动建模和真实打印校准仍需人工验收。
- **发布前检查：已实现**。检查保护区、边界、物理尺寸、识别模式/填写方式兼容、核心工资模板业务约束和拼版。
- **数量**：源码种子函数当前返回 **30 个已发布版本、20 个模板键**，纸张为 A4/A5。由于本次按要求未读取运行数据库，当前本机实际安装数量不能确认。（代码：`app/modules/templates/seed_templates_ds.py`、`payroll_profiles_ds.py`、`core_payroll_layouts_ds.py`）
- **岗位复用：已实现**。6 个核心布局与多个岗位 profile 绑定，避免每岗位复制整套坐标。
- **纸质模板与统计报表：已区分**。前者是 `template_versions`，后者是 `report_definition_versions`；但标准事实层仍不够严格，见第 12 节。

指定表单核对：

- **竹丝装笼跟踪牌：未实现**。当前代码和测试没有该名称或对应模板键；“竹丝装架日工资表”不是同一张表，不能视为已落地。
- **配片数计量考核表：未实现**。当前代码和测试没有该名称或对应模板键。

# 10. 识别和审核流程

| 步骤 | 状态 | 输入 → 输出 | 失败/重试与代码 |
|---|---|---|---|
| 图片导入 | **已实现** | JPEG/PNG/TIFF 原始字节（≤20MB）→ 表单、原图、缩略图、task。 | 类型/大小/解码失败返回 415/413/422；同一幂等键可重放。`app/api/routers/imports_ds.py` |
| 去重 | **已实现** | SHA-256 → 新表单或已有表单引用。 | 重复返回 409；不会重复保存。原始证据在退回/作废后仍保留。 |
| 模板分类 | **部分实现** | QR/双 QR → 已发布模板/岗位版本。 | 无码或无效码进入 `NEEDS_CLASSIFICATION`；冲突记录审计。可人工选择。`recognize_forms.py`、`classification_ds.py` |
| 图像质量 | **接口/占位** | 已有模糊/过暗/过亮检测函数。 | 当前导入路由未调用，因此不会自动进入重拍状态。`opencv.py`、`RecognizeForms.assess_quality` |
| 图像校正 | **部分实现** | 四角 ArUco + 页面规格 → canonical PNG。 | 缺标记时导入任务只记录“跳过校正”并继续，不自动要求重拍。重试需重新导入或后续人工处理。 |
| 字段裁切 | **已实现（依赖校正）** | 已发布模板规范化坐标 + 校正图 → 永久字段裁片、`form_fields`。 | 校正被跳过时不会裁片；单个持久化失败会删除刚写文件。 |
| OCR/OMR | **部分实现** | 单字段裁片 → 候选值、置信度、引擎/模型版本。 | 仅 `digit_template` 单格数字与 `omr`；其他返回无候选，转人工。 |
| 人工分类后识别 | **接口/占位** | 人工绑定模板 → `FORM_RECOGNITION` task。 | 当前没有 handler/worker 消费该任务，可能长期 PENDING；这是当前闭环缺口。 |
| 候选值 | **已实现** | `recognition_attempts` → 工作台字段 candidates。 | 多次候选可追溯到裁片；没有自动覆盖正式值。 |
| 规则校验 | **已实现基础** | 电子值 + 模板字段规则 + 主数据 → 字段级错误。 | 必填、数值范围、枚举、主数据、人工确认约束可阻断确认；复杂跨字段/工资规则不完整。`review/facade_ds.py` |
| 人工审核 | **已实现** | 原/校正图、裁片、候选、电子表格 → 草稿或确认记录。 | 需持有 lease；冲突/过期需刷新并重新获取。 |
| 确认记录 | **已实现** | values + expected version + evidence → append-only `record_version`。 | `If-Match` 过期返回冲突；成功可原子认领下一张。 |
| 更正 | **已实现** | 已确认记录 + 原因 → 新 `CORRECTED` 版本。 | 已导出记录会标记 `REEXPORT_REQUIRED`。 |
| 退回/作废 | **已实现** | 原因 + evidence → 状态/审计或 VOID 版本。 | 权限、lease、版本均校验。 |
| 重导 | **已实现** | 新记录版本 + 原批次 ID → 新导出批次并建立 supersedes 链。 | 输入为空、映射/文件校验失败会生成安全任务错误。 |

当前流程不是“任意图片均可 OCR”：只有含当前已发布模板 QR 且四角标记完整的纸张才能自动走到裁片；普通照片会进入人工分类，而人工分类后的真正识别执行尚未接通。

# 11. 基础数据和业务规则

| 能力 | 状态 | 说明 |
|---|---|---|
| 员工 | **已实现** | 独立 catalog；编码、名称、active、revision；属性 JSON 含班组、岗位、电话、备注。 |
| 班组 | **部分实现** | 员工属性/表单字段，没有班组实体、负责人、成员关系或版本。 |
| 工单 | **已实现** | catalog + 产品、计划数量、日期、负责人等 JSON 属性。 |
| 产品/规格 | **已实现/部分实现** | 产品 catalog 已有；规格和单位是 JSON 属性，不是独立受控实体。 |
| 工序 | **已实现** | catalog + 标准顺序、工位属性。 |
| 设备 | **未实现** | 无 catalog/表/API。 |
| 供应商 | **未实现** | 无 catalog/表/API。 |
| 单价 | **部分实现/配置占位** | 模板字段和岗位 `pricing_rules` JSON 可保存，但无主数据价目表和计算服务。 |
| 工资规则 | **接口/占位** | 有 calculation expression、pricing/deduction JSON 和“系统计算”字段语义，当前没有表达式执行/规则版本计算引擎。 |
| 奖励与扣减 | **接口/占位** | 可作为字段/JSON 配置保存，未形成统一可执行规则。 |
| 生效日期/规则版本 | **未实现** | 岗位配置有版本号，但没有完整 effective_from/to、审批和按日期选规则机制。 |

主数据实现位于 `app/modules/master_data/`、`app/api/routers/master_data_ds.py`；当前只有四种 catalog。电子填报至少还需班组/成员、设备、价格表、规则版本和有效期，以及明确的工序填报责任。

# 12. Excel 和报表能力

- **XLSX 导出：已实现**。openpyxl 可输出通用四工作表、字段映射明细、DETAIL、SUMMARY 和 FIXED 报表。（代码：`app/adapters/export/xlsx.py`）
- **Excel 模板读取：部分实现**。只读取代码内登记的固定 `.xlsx` 资产；发布定义保存模板键和 SHA-256。
- **字段映射：已实现**。模板字段 export target、报表列、固定单元格和固定表格列均可映射，并在批次中快照。
- **样式/合并单元格：已实现于固定模板模式**。openpyxl 加载原工作簿并只写指定单元格，因此未改动区域的样式和合并结构会保留。
- **公式：明确不支持固定模板公式**。加载后发现任意公式即拒绝；外部链接和宏也拒绝。这是安全策略，不是公式保留能力。
- **导出预览/排除原因：已实现**。确认状态、模板、映射和最终字段校验决定 included/excluded。
- **批次、重导、追溯：已实现**。批次保存记录版本、模板/映射快照、映射哈希、文件哈希、操作者和 supersedes。
- **企业上传固定统计模板：未实现**。没有上传/校验/登记 UI 或 API；当前只有仓库内置 `legacy_timekeeping_daily.xlsx`。
- **多个纸质表生成汇总表：已实现基础**。SUMMARY 报表可对多个已确认记录 group/sum/count/min/max/average。
- **工资规则计算层：未实现**。报表只读取已确认值和少量别名/数量汇总，不执行岗位工资公式。

目标分层现状：

```text
纸质采集表（已实现）
  → 标准业务事实（部分实现：record.values 仍是模板字段 JSON，别名靠导出适配）
  → 规则计算（未实现：只有表达式/规则配置）
  → 固定汇总模板（部分实现：内置固定模板可用，企业上传不可用）
```

因此当前尚未真正完成稳定的“标准事实模型 + 可版本化工资计算层”。`app/adapters/export/xlsx.py` 中 `_report_value` 的别名映射正是该缺口的证据。

# 13. AI / DeepSeek 接入现状

- **DeepSeek：部分实现且默认关闭**。仅当 `FORM_DEMO_AI_ENABLED=true` 且提供 API key 时，导出中心只读报表助手才调用 DeepSeek chat completions。（代码：`config/settings.py`、`app/services/container.py`）
- **调用位置**：`app/adapters/ai/deepseek_ds.py`；入口 `POST /api/v1/exports/assistant`。
- **提示词**：代码内构建，无独立 prompt 文件；规则明确只读、不得执行代码或修改/发布/删除。
- **输入**：用户问题、选中的报表定义 ID、有限预览摘要和已发布报表 catalog；不直接发送图片或整个数据库。
- **输出**：JSON object，经严格 Pydantic `ReportAssistantProposal(extra=forbid)` 校验；使用 `response_format=json_object`，但没有把完整 JSON Schema 发送给供应商。
- **脱敏：未实现通用脱敏器**。输入结构被限制，但问题文本和预览摘要不会自动掩码；生产接入前必须定义敏感字段白名单。
- **日志/审计：不足**。客户端不主动记录 prompt/response，助手调用也没有独立审计记录、模型版本和耗时记录。
- **超时/降级：已实现基础**。默认 20 秒，最大 60 秒；任何异常返回 `UNAVAILABLE`，不阻断人工导出。
- **写权限：没有**。报表助手只能返回回答、建议定义/筛选和下一步；前端仍需用户操作。
- **通用 AI 审核：接口/占位**。严格 `AIReview`、持久表和应用服务存在，但当前容器始终注入 `DisabledAIReview`，且无主 API 路由触发。（代码：`app/adapters/ai/contracts.py`、`app/application/ai_review_forms.py`）

必须保持的目标边界：**AI 只允许问答、解释、模糊需求理解和配置草案，不得直接修改正式数据、模板、工资公式或触发不可逆操作。** 任何未来 AI 配置草案必须经过确定性校验、权限检查和人工确认后，才由非 AI 应用服务执行。

# 14. 身份、权限和审计

- **登录：未实现**。没有登录页、会话、密码、OIDC 或 Token 验证。
- **当前用户模型：已定义**。`Actor(actor_id, roles, authenticated, local_full_access)`；角色 ADMIN/OPERATOR/REVIEWER/FINANCE/AUDITOR，权限枚举较完整。
- **默认模式：本地完整权限**。默认 actor 为 `local-operator`，即使配置角色为 OPERATOR，`local_full_access` 会绕过角色限制。（代码：`config/settings.py`、`app/api/dependencies_ds.py`）
- **请求头身份：仅测试/受控配置**。`allow_header_identity` 默认 false；它不是安全认证，不能用于公网。
- **审计：部分实现**。业务事件记录 actor、前后值摘要、原因和 evidence ID；主数据另有 revision audit。默认单一 actor 导致多人时无法真实追责。
- **500 人缺口**：必须新增真实身份提供方、会话/短期令牌、组织/班组范围、最小权限、设备登记、登录/登出/失败审计、撤权、数据库与对象存储、独立 worker、限流、可观测性、备份演练和高可用部署。
- **班组公共设备模式**：技术上可实现，但不能继续使用默认 actor；需设计快速换人、工牌扫码、班组设备身份、超时锁屏、未提交草稿归属和主管接管。
- **员工工牌二维码**：OpenCV 已能解二维码，员工主数据也能查编码，所以后端校验较容易复用；手机实时扫码 UI、二维码签名/防伪、员工与设备会话绑定及审计仍需新增。

# 15. 测试现状

本次只运行不访问业务数据库/上传目录的源码测试与静态检查。

- Python：59 个测试文件，源码中 345 个普通测试声明；参数化收集后本次实际 **381 passed，0 failed，0 skipped，179.48 秒**。
- Python 测试类型：unit 18 文件、api 12、application 2、adapters 2、integration 18、modules 5、architecture 1、tools 1。
- Ruff：`ruff check app config tests --no-cache`，本次通过。
- mypy：`mypy app config`（临时缓存放在仓库外），本次检查 136 个源码文件并通过。
- 前端：36 个 Vitest 测试文件、源码统计 142 个 `it/test` 声明，覆盖路由、审核、图片、批量导入、模板设计、基础数据、导出和 API 客户端。
- 前端本次结果：**未复验**。按本任务限制未读取 `node_modules`，也未执行会生成包 `dist` 的 `npm test/typecheck/build:web`，因此不能声称当前通过。
- 集成测试：数据库迁移、仓储、识别、XLSX、备份完整性等已存在。
- 端到端：**未实现**。无 Playwright/Cypress，也没有真实浏览器—API—数据库—文件系统全链路测试。
- 仍缺：手机真机与触控、弱网/断网、Service Worker 更新、IndexedDB 迁移、离线队列、重复点击/重放、多人审核并发、500 用户负载、局域网 HTTPS、相机权限、超大批次和存储耗尽测试。

实际命令定义见 `pyproject.toml`、`frontend/package.json`、`frontend/apps/web/package.json`。旧文档中的测试数量不是当前代码基线；本节以本次收集与执行为准。

# 16. PWA 改造基础评估

| 问题 | 结论 |
|---|---|
| 可直接增加移动端路由 | **可以**。React Router 与 API 已分开，但需设计独立的填写/扫码/草稿流程，不能只缩小桌面审核页。 |
| 响应式基础 | **已有部分基础**，模板库、审核、主数据、导出有断点。 |
| Manifest / Service Worker | **未实现 / 未实现**。 |
| IndexedDB / 离线草稿 / 提交队列 | **未实现 / 未实现 / 未实现**。当前草稿只在服务器。 |
| 请求幂等 | **部分已有**。导入/导出/任务有幂等；未来电子填报提交需专门的 client_submission_id 和服务端唯一约束。 |
| 二维码扫码 | **后端图片解码已实现；移动实时扫码未实现**。 |
| 手机相机上传 | **接口/占位**。`WebCameraPort` 能调用 `getUserMedia`，但当前产品页面未使用；文件选择可能由手机浏览器提供拍照入口，但无 `capture` 流程。 |
| HTTPS | **未配置**。相机、Service Worker 和安全登录通常要求可信 HTTPS。 |
| 局域网部署 | **可改造，不可直接生产使用**。需监听非 loopback、反向代理 TLS、真实认证、防火墙、稳定主机、PostgreSQL/对象存储和备份。 |

可复用：模板/岗位版本、字段规则、主数据查询、记录版本、审核锁、审计、任务幂等、导出、ProblemDetails、手写 API 客户端的业务语义、shell ports 抽象。

必须新增：移动填报路由和专用 DTO、Manifest/图标、Service Worker、IndexedDB 数据模型、离线草稿与 outbox、同步状态/冲突 UI、认证、设备/工牌扫码、HTTPS 部署、提交幂等、网络恢复与更新策略。

不应放入首批移动端：完整模板设计器、固定 Excel 模板配置、批量财务导出、系统级强制释放/清理、复杂审计管理。移动端优先做班组填报、拍照/扫码、本人草稿、提交状态与必要的退回修改。

# 17. 微信小程序迁移边界

- **API 与页面解耦：大部分已解耦**。React 通过 `/api/v1` 调用 FastAPI；但 DTO 为手写，需先稳定 OpenAPI 合同。
- **表单配置由后端提供：已实现基础**。模板版本、字段、规则、岗位配置可通过模板 API 获取。
- **核心计算在后端：部分成立**。校验、版本、审计和导出在后端；工资公式执行不存在，部分即时提示在前端重复实现。
- **可共享 TypeScript**：`api-client` 的纯 DTO、状态枚举、错误模型和部分纯函数可迁移；当前 `generated_ds.ts` 未生成，建议先建立自动生成/兼容层。
- **不能直接共享 UI**：React DOM 组件、CSS、`<input type=file>`、浏览器通知、`window.confirm`、DOM canvas 和 React Router 页面不能直接用于微信小程序。
- **浏览器依赖**：`fetch`/DOM `File`、`crypto.randomUUID`、`localStorage`、`beforeunload`、Notification、MediaDevices、Object URL 以及 Vite 路由/代理。
- **未来可复用接口**：模板读取、主数据、导入、分类、工作台详情、审核确认/退回/作废、任务状态、导出预览可在认证和 DTO 稳定后复用。桌面文件选择和下载交互需小程序适配器。

# 18. 已知问题和技术债

按优先级：

1. **P0—人工分类后识别不执行**：API 只创建 `FORM_RECOGNITION` task，无 worker/handler；任务可能永久 PENDING。（`app/api/routers/classification_ds.py`、`app/infrastructure/tasks/in_process_ds.py`）
2. **P0—无真实身份认证**：默认本地 actor 拥有完整权限，多人或局域网开放将失去安全边界和真实审计。（`config/settings.py`、`app/api/dependencies_ds.py`）
3. **P0—工资计算层缺失**：模板声明“系统计算”字段和表达式，但没有执行引擎；不可把当前导出当作正式工资核算。（`core_payroll_layouts_ds.py`、`app/adapters/export/xlsx.py`）
4. **P1—图像质量检测未接入**：已有检测函数但导入不调用；缺标记只跳过校正，未自动进入重拍。（`imports_ds.py`、`opencv.py`）
5. **P1—任务架构不一致**：导入同步、导出 FastAPI 后台任务、线程运行器未接入；进程级任务不适合多实例。（`services/container.py`、`in_process_ds.py`）
6. **P1—本地 SQLite/文件系统容量与并发**：永久裁片、无配额/归档、单机路径、SQLite 写竞争，不适合 500 人。（`local.py`、`sqlite_ds.py`）
7. **P1—PWA 栈为空**：无 Manifest、SW、IndexedDB、离线队列、HTTPS 和移动提交合同。
8. **P1—固定 Excel 模板不能由企业上传**：只有代码内置资产；公式一律拒绝，复杂企业模板兼容性有限。（`app/adapters/export/xlsx.py`）
9. **P1—AI 无脱敏和调用审计**：虽然只读且默认关闭，但问题文本没有自动脱敏，调用元数据也未留痕。（`app/application/report_assistant_ds.py`）
10. **P2—通用 OCR 缺失**：只支持单格数字模板和 OMR；中文/手写数字串依赖人工。（`app/adapters/recognition/digits.py`）
11. **P2—API 类型手工维护**：OpenAPI 生成文件为占位，前后端 DTO 可能漂移。（`frontend/packages/api-client/src/generated_ds.ts`）
12. **P2—前端样式集中**：单一大 CSS、无视觉回归/真机 E2E，移动改造回归成本高。（`frontend/apps/web/src/styles.css`）
13. **P2—文档与代码差异**：旧文档测试数量已过时；“待实现”的 PWA/Tauri 不能被视为现成功能；运行数据库模板数量也不能由源码种子数量替代。
14. **P2—指定业务表未落地**：“竹丝装笼跟踪牌”“配片数计量考核表”均未在模板代码中实现。

# 19. PWA 开发前必须确认的问题

以下无法从代码确定，必须由业务人员回答：

1. 竹丝装笼跟踪牌的每个工序分别由谁填写、何时交接、谁最终确认？
2. 配片数计量考核表由工人、班组长、质检还是计薪人员填写；各自可见和可改哪些字段？
3. 现场主要使用班组公共设备还是个人手机；公共设备如何快速切换操作者？
4. 车间网络最差情况下可连续离线多久，是否存在完全无 Wi-Fi/蜂窝网络的区域？
5. 上线后是否长期保留纸质兜底；纸质与电子记录冲突时以谁为准？
6. 身份识别采用工号+姓名、工牌二维码、账号密码、企业微信，还是多种组合？
7. 每张表的审核顺序是什么，哪些表必须经过班组长、质检和财务的串行确认？
8. 离线草稿允许保存多久；设备丢失或换人时草稿如何转移/清除？
9. 提交后是否允许填写人修改，允许到哪个状态；修改是否必须填写原因？
10. 谁能退回、作废、恢复或强制接管审核；是否需要双人复核？

# 20. 建议的 PWA 改造切入点

以下仅为开发顺序，不在本次实施。

## 阶段 1：冻结移动业务合同与两张目标表

- **目标**：明确填写角色、字段、状态、标准事实 DTO，并把两张目标表建成可测试规范。
- **涉及模块**：templates、master_data、domain、API schemas。
- **建议读取**：`app/domain/templates_ds.py`、`app/modules/templates/core_payroll_layouts_ds.py`、`app/api/schemas/`。
- **建议修改**：新增目标模板定义、电子填报 DTO/领域对象和合同测试；不要先改 UI。
- **验收**：两张表字段/角色/规则经业务签字；OpenAPI 能表达草稿、提交和冲突。
- **局部测试**：模板 domain/preflight/API tests。
- **风险**：业务责任不清会导致后续离线模型返工。
- **数据库迁移**：可能需要（电子提交/填写会话实体）。

## 阶段 2：修复现有识别任务闭环

- **目标**：人工分类后真正执行校正、裁片和识别；统一任务状态。
- **涉及模块**：classification、recognition、tasks。
- **建议读取**：`classification_ds.py`、`imports_ds.py`、`recognize_forms.py`、`in_process_ds.py`。
- **建议修改**：识别 handler、任务调度/恢复和失败状态；避免复制导入逻辑。
- **验收**：人工分类任务必达终态，成功后工作台出现字段/候选，失败可重试且审计完整。
- **局部测试**：classification/import/task API 与 recognition integration tests。
- **风险**：文件与数据库事务跨界、重复裁片。
- **数据库迁移**：通常否，除非增加专用 recognition job 字段。

## 阶段 3：建立真实认证与设备/班组身份

- **目标**：替换 local full access，支持个人与公共设备的可审计身份。
- **涉及模块**：identity_access、API middleware、frontend shell。
- **建议读取**：`identity_access/*`、`dependencies_ds.py`、`AppShell.tsx`。
- **建议修改**：认证适配器、会话、登录/扫码绑定、组织范围和安全审计。
- **验收**：每次写操作可追溯真实人员；权限越权测试通过；默认身份不能进入生产。
- **局部测试**：identity/policy/API authorization tests。
- **风险**：公共设备换人、令牌泄漏、弱网续期。
- **数据库迁移**：是。

## 阶段 4：新增移动填写路由和服务端草稿

- **目标**：用后端模板配置渲染手机友好的分步表单，不搬运桌面模板设计器。
- **涉及模块**：React routes、api-client、templates、records。
- **建议读取**：`app/router.tsx`、`ReviewWorkbenchPage.tsx`、`templates_ds.ts`、review API。
- **建议修改**：`/mobile/forms/*` 页面、电子草稿/提交 API、字段分组组件。
- **验收**：360px 宽单手填写；必填/范围/主数据与后端一致；刷新可恢复草稿。
- **局部测试**：移动组件 Vitest + API contract tests。
- **风险**：前后端校验漂移、长表单性能。
- **数据库迁移**：可能需要。

## 阶段 5：PWA 外壳与安全更新

- **目标**：可安装、可更新、静态外壳离线可打开。
- **涉及模块**：Vite、Web assets、部署。
- **建议读取**：`vite.config.ts`、`main.tsx`、`AppShell.tsx`。
- **建议修改**：Manifest、图标、Service Worker、版本提示和缓存白名单。
- **验收**：Lighthouse PWA 基础项通过；更新不丢草稿；API/证据/用户数据不被错误永久缓存。
- **局部测试**：SW 单元测试 + Playwright 离线/更新场景。
- **风险**：旧缓存、敏感响应缓存。
- **数据库迁移**：否。

## 阶段 6：IndexedDB 离线草稿与 Outbox

- **目标**：断网可持续填写，联网后按幂等键提交并显示冲突。
- **涉及模块**：mobile frontend、API idempotency、records/tasks。
- **建议读取**：`tasks_ds.py`、`review-workbench.ts`、现有草稿/版本代码。
- **建议修改**：IndexedDB schema、draft/outbox/sync adapter、提交唯一键和冲突 API。
- **验收**：断网创建/编辑/重启不丢；重复同步只产生一条正式记录；冲突不静默覆盖。
- **局部测试**：fake-indexeddb + API idempotency + Playwright 网络切换。
- **风险**：设备共用数据泄漏、schema 升级、时钟与排序。
- **数据库迁移**：是，建议保存 client submission identity。

## 阶段 7：工牌二维码与手机拍照

- **目标**：快速绑定操作者/工单并采集必要证据。
- **涉及模块**：shell-ports、mobile UI、identity、imports/evidence。
- **建议读取**：`shell-ports/src/web_ds.ts`、`imports_ds.py`、master data API。
- **建议修改**：扫码适配器、相机页面、压缩/方向校正、二维码签名校验。
- **验收**：Android/iOS 主流浏览器权限、后摄切换、弱光/取消/拒绝均有清晰恢复路径。
- **局部测试**：适配器单测 + 真机验收脚本。
- **风险**：HTTPS、权限差异、伪造二维码、图片体积。
- **数据库迁移**：可能需要设备/工牌绑定表。

## 阶段 8：标准事实与版本化工资规则

- **目标**：落实“采集表 → 标准事实 → 规则计算 → 报表”，禁止在导出层临时猜字段。
- **涉及模块**：domain、job profiles、master data、reporting。
- **建议读取**：`core_payroll_layouts_ds.py`、`export/xlsx.py`、`reporting/models_ds.py`。
- **建议修改**：标准事实 schema、价格/规则版本和确定性计算服务；移除新增别名债务。
- **验收**：相同事实+规则版本得到相同工资；有效期、舍入、奖励/扣减和更正可追溯。
- **局部测试**：规则单元/性质测试、历史版本重算与报表集成测试。
- **风险**：工资法律/业务口径、舍入与历史追溯。
- **数据库迁移**：是。

## 阶段 9：生产数据与文件基础设施

- **目标**：从单机 SQLite/本地文件迁移到 PostgreSQL + 可配置对象/NAS 存储 + 独立 worker。
- **涉及模块**：database、storage、tasks、backup、deployment。
- **建议读取**：`sqlite_ds.py`、`models.py`、`review/repository_ds.py`、`local.py`、`backup/`。
- **建议修改**：数据库/存储 ports、PostgreSQL migrations、对象存储适配器、任务队列、TLS 部署和可观测性。
- **验收**：并发/故障恢复/备份演练通过；500 用户容量目标有压测证据；文件与记录不孤儿。
- **局部测试**：PostgreSQL 集成、对象存储契约、并发/恢复/负载测试。
- **风险**：迁移停机、对象一致性、成本和运维能力。
- **数据库迁移**：是。
