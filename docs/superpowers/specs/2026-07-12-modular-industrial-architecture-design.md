# 模块化工业程序增量架构设计

## 1. 目标与约束

本次优化在不改写现有业务闭环的前提下，为多人协作、React 前端、Web/Tauri 双壳、服务器部署和工业设备接入补齐基础架构。现有领域实体、应用服务、SQLite、本地证据、识别、规则、审计、查询、导出和可选 AI 能力继续使用。

当前仓库尚无 FastAPI 实现；本次新增 FastAPI 接口层。系统保持模块化单体，不提前拆分微服务。模块间通过 Application Port、公开用例和领域事件协作，不直接依赖其他模块的数据库 Adapter。

## 2. 总体结构

```text
React Feature Modules
  ├─ Web Shell
  └─ Tauri Desktop Shell
          ↓ OpenAPI + SSE
FastAPI API Layer (/api/v1)
          ↓ Application Use Cases / Ports
Modular Domain Core
          ↓ Repository / Infrastructure Ports
SQLite · Local Files · In-process Tasks · Local Index
```

未来可在不修改业务规则的情况下，将基础设施替换为 PostgreSQL、NAS/S3、Worker 队列和 Qdrant。识别、AI、向量和音频转写是可选模块，关闭或不可用时不得阻断核心流程。

## 3. 后端模块边界

后端采用以下业务模块，但初期仍可复用现有实体和应用服务，避免机械搬迁文件：

| 模块 | 责任 | 公开接口 |
|---|---|---|
| `forms` | 表单、字段、状态机、当前版本 | Form queries、状态转换 |
| `templates` | 模板、坐标、字段映射、版本 | Template catalog、coordinate schema |
| `evidence` | 原图、裁切、录音、哈希、只读约束 | Evidence store/read ports |
| `recognition` | 分类、图像处理、OCR、OMR、Attempt | Recognition jobs、candidate queries |
| `review` | 草稿、确认、更正、作废、审核锁 | Review commands、lease commands |
| `rules` | 确定性规则和字段级错误 | Validation service |
| `master_data` | 员工、工单、产品、工序 | Master-data queries/import |
| `search` | 精确筛选和相似引用 | Structured search、similarity references |
| `reporting` | 指标、图表、XLSX 和导出批次 | Dashboard queries、export jobs |
| `audit` | AuditEvent、版本和血缘 | Timeline、trace queries |
| `tasks` | 长任务、进度、取消、重试 | Task commands、event stream |
| `identity_access` | 用户、角色、权限策略 | Identity context、policy checks |

新增 `app/modules/` 作为模块入口和装配边界。现有 `app/domain`、`app/application`、`app/adapters` 暂不整体迁移；模块 Facade 调用现有用例，后续按业务变化逐步内聚。

## 4. Repository、Port 与 Adapter

- Domain 不导入 FastAPI、SQLAlchemy、Streamlit、React 或设备 SDK。
- Application 定义 Repository、Task、Storage、Identity、Clock 和 Event Port。
- Adapter 实现 SQLite/PostgreSQL、Local/NAS/S3、InProcess/Worker、Local/Qdrant 等端口。
- API 和 UI 只调用 Application Facade，不直接创建 SQLAlchemy Session 或访问文件路径。
- 端口类型按能力拆分，避免一个 Repository 同时承担表单、证据、审计和导出全部职责。
- 现有 `SqlAlchemyFormRepository` 先由兼容 Facade 包装，后续再按模块拆分，不在本次强制重写。

## 5. 后台任务编排

首版实现可替换的任务系统：

- `TaskPort`：submit、get、cancel、retry、list_events。
- `InProcessTaskRunner`：单机线程池或受控执行器。
- `SQLiteTaskStore`：任务状态和事件持久化，重启后保留失败与完成记录。
- 状态：`PENDING | RUNNING | SUCCEEDED | FAILED | CANCEL_REQUESTED | CANCELLED`。
- 事件：queued、started、progress、warning、completed、failed、cancelled。
- 每个事件包含 task_id、sequence、timestamp、event_type、progress、message、payload。
- 幂等键用于导入、识别和导出任务，避免重复提交。
- 长任务不得直接持有 Web 请求；API 返回 202 和 task_id。

未来 Worker Adapter 可替换执行器与任务存储，Application 层接口不变。

## 6. 用户、角色和权限

首版身份上下文由可替换 `IdentityProvider` 提供。单机模式使用本地用户；服务器模式可接企业 SSO。

角色：

- `ADMIN`：系统配置、用户、模板和全部数据。
- `OPERATOR`：导入、分类和草稿录入。
- `REVIEWER`：确认、更正、作废和审核锁。
- `FINANCE`：查询、预览、导出和导出批次。
- `AUDITOR`：只读追溯、审计和证据访问。

权限使用细粒度枚举，例如 `form.read`、`review.confirm`、`export.create`、`evidence.audio.read`。FastAPI Dependency 统一执行策略；领域层对关键操作仍验证 actor 和业务约束，不能只依赖前端隐藏按钮。

## 7. 多人审核锁与并发控制

采用两层控制：

1. `ReviewLease`：form_id、owner_id、lease_token、acquired_at、expires_at、heartbeat_at。锁过期后可重新获取；管理员可带原因强制释放。
2. RecordVersion 乐观并发：确认或更正必须提交 `expected_version`。版本不一致返回 409，不自动覆盖。

API：acquire、heartbeat、release、force-release。确认事务验证 lease_token、owner、过期时间和 expected_version，并生成 AuditEvent。浏览器断开不会无限占锁；Desktop/Web Shell 均定时续租。

## 8. API 与实时事件契约

- API 前缀：`/api/v1`。
- DTO 使用 Pydantic，与领域实体分离。
- 错误采用 Problem Details 风格：type、title、status、detail、code、request_id、field_errors。
- 写操作支持 `Idempotency-Key`；版本写入支持 `If-Match` 或 DTO expected_version。
- OpenAPI 是 React API Client 的唯一生成来源。
- 长任务进度首版使用 SSE：`GET /api/v1/tasks/{task_id}/events`。
- 事件以递增 sequence 支持断线续传；客户端通过 `Last-Event-ID` 恢复。
- WebSocket 仅在未来需要双向设备控制时增加，不与首版 SSE 并行维护。

首批 API 覆盖健康检查、当前身份、任务、审核锁、表单详情、证据读取和审核确认；其他现有用例按 React 迁移顺序开放。

## 9. 日志、健康检查与错误追踪

- 统一结构化日志：timestamp、level、request_id、actor_id、module、event、form_id、task_id、duration_ms。
- 中间件生成或透传 `X-Request-ID`。
- `/health/live` 只验证进程存活。
- `/health/ready` 验证数据库、迁移版本、证据目录可读写和任务执行器可用；可选 AI/向量不可用不影响 ready，但写入 capability 状态。
- 全局异常处理器将内部异常映射为稳定错误码，不泄露文件绝对路径、SQL 或秘密。
- `ErrorTracker` Port 默认本地日志实现，服务器可替换为 Sentry/OpenTelemetry。

## 10. 数据库迁移、备份和一致性

- 建立 Alembic 基线，禁止运行时仅依赖 `Base.metadata.create_all` 升级生产数据库。
- 开发环境可创建空库；已有 Demo 数据库通过基线标记迁移。
- `BackupService` 使用 SQLite Online Backup API 生成一致数据库快照。
- 备份清单包含数据库、证据文件、导出文件、schema revision、大小和 SHA-256。
- `ConsistencyChecker` 检查数据库外键、缺失证据、哈希不匹配、孤立裁切、缺失导出和当前版本指针。
- 恢复先验证清单和迁移版本，再切换数据目录；失败不得覆盖当前运行数据。

## 11. React Feature 与双 Shell 边界

本次只创建边界和契约骨架，不完成全部产品页面：

```text
frontend/
  apps/web/
  apps/desktop/
  features/review-workbench/
  features/task-queues/
  features/master-data/
  features/templates/
  features/dashboard/
  features/exports-trace/
  shared/api-client/
  shared/design-system/
  shared/shell-ports/
```

Shell Ports：FilePort、CameraPort、ScannerPort、AudioPort、NotificationPort。Web Shell 使用浏览器实现；Tauri Shell 使用原生命令实现。Feature Module 不导入 Tauri API，也不直接调用浏览器文件系统。

## 12. Streamlit 渐进迁移

1. 修复 Streamlit 自动 pages 空白入口，并标记为诊断界面。
2. 新增 FastAPI 和 OpenAPI；Streamlit 业务逻辑暂继续调用同一 Application Facade。
3. React 首先实现审核工作台和任务队列。
4. React 再迁移模板、主数据、查询、驾驶舱和导出。
5. 功能验收后，Streamlit 仅保留管理员诊断页，最终可移除。

迁移期间 SQLite 仍是唯一事实源，不允许 React 或 Streamlit 各自维护业务状态。

## 13. 测试与完成标准

- 现有测试必须保持通过。
- 新增任务状态机、取消、失败和幂等测试。
- 新增权限矩阵和越权拒绝测试。
- 新增锁获取、续租、过期、强制释放和 409 冲突测试。
- 新增 OpenAPI、Problem Details、SSE 顺序与断线续传测试。
- 新增健康检查、结构化日志和可选服务降级测试。
- 新增 Alembic 空库迁移、已有库基线、备份恢复和一致性检查测试。
- 新增 Shell Port TypeScript 契约测试或类型检查。
- 更新架构、运行、迁移、备份、恢复和多人协作文档。

完成后，核心业务在 AI、向量和音频转写关闭时仍能运行；API、任务、权限、审核锁和迁移机制具备自动化证据；React/Tauri 可在稳定边界上继续开发。
