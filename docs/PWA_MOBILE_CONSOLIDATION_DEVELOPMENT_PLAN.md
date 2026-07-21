# PWA 移动端电子填报整理与主系统接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 保留现有移动端交互原型和 PWA 外壳，替换独立内存后端，把电子填报接入主系统的身份、模板、主数据、审核、审计和导出闭环。

**Architecture:** 移动端只是新的采集入口，不建立第二套业务系统。`/api/v1/mobile` 作为移动协议层，调用新的 `electronic_forms` 应用模块；提交先写入现有 `forms`、`form_fields` 和 `audit_events`，审核确认后沿用现有流程生成 `record_versions`，离线发件箱由浏览器 IndexedDB 管理。

**Tech Stack:** Python 3.11、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、SQLite（当前）/PostgreSQL（后续）、React 18、TypeScript、Vite、vite-plugin-pwa、IndexedDB、Vitest、pytest。

---

## 0. 文档依据与适用范围

本计划依据 `codex/low-token-ui-v2` 工作树中尚未提交的实际代码编写，基线提交为 `574dea0`。已核对：

- `app/api/routers/mobile_ds.py`
- `app/modules/mobile/models_ds.py`
- `frontend/apps/web/src/mobile/`
- `frontend/apps/web/src/pwa/`
- `frontend/apps/web/src/app/router.tsx`
- `frontend/apps/web/vite.config.ts`
- 现有身份、模板、主数据、审核、任务、导出和数据库模块

本计划不把当前原型描述为生产功能。当前代码可以演示“登录 → 选表单 → 填写 → 提交 → 查看记录”，但身份、表单定义、生产上下文、草稿、提交和发件箱都绕开主系统。

### 分支纪律

- 不创建新分支。
- 整理工作继续在现有 `codex/low-token-ui-v2` 完成。
- 每个任务单独提交，禁止把业务表格、运行数据、缓存或无关修改混入提交。
- 全部验收通过后，将 `modular-architecture` 快进到验收提交。
- 快进前先处理两个工作树各自未提交内容；不得用 reset、checkout 或清理命令覆盖现有修改。
- 合并完成后停止继续使用 `codex/low-token-ui-v2`，后续开发回到 `modular-architecture`。

## 1. 当前原型判定

### 可以保留

| 能力 | 当前文件 | 整理方向 |
|---|---|---|
| 移动端布局与底部导航 | `MobileLayout.tsx` | 保留，补路由守卫和无障碍状态。 |
| 首页、记录、草稿、提交、个人页 | `frontend/apps/web/src/mobile/*Page.tsx` | 保留交互意图，数据源改为正式 API/IndexedDB。 |
| 三种填报交互原型 | Bamboo/Sheet/Team 页面 | 作为业务规格样本，不直接认定为正式表单。 |
| 七种字段呈现策略 | `MobileFormEngine.tsx` | 保留概念，拆分 reducer、计算、校验和渲染器。 |
| SELF / TEAM_LEADER_BATCH | 前后端类型 | 保留，服务端增加真实角色和班组成员校验。 |
| PWA Manifest、安装和更新提示 | `public/`、`src/pwa/` | 保留，收紧缓存边界并增加更新验收。 |
| `client_submission_id` | submission API | 保留，改为数据库唯一约束和必填请求头。 |

### 必须替换，不能进入生产路径

| 当前实现 | 问题 | 替换目标 |
|---|---|---|
| `_users/_sessions/_form_schemas/_drafts/_submissions/_outbox` | 重启丢失、进程不共享、无事务 | SQLAlchemy 仓储与正式应用服务。 |
| 张三/李四、PIN 1234 | 硬编码身份，PIN 哈希弱且无锁定 | 员工主数据 + 凭据/会话仓储 + 限速锁定。 |
| 固定笼号、工单、产品和班组成员 | 与生产数据脱节 | 主数据、班组成员和生产资源查询。 |
| `dict[str, Any]` 请求体 | 无结构化校验 | Pydantic 请求/响应模型。 |
| 前端计算即提交 | 可伪造金额、数量和身份 | 服务端重建锁定值并重新计算。 |
| 服务端 `_outbox` | 从未写入，不是真正离线队列 | IndexedDB outbox + 同步协调器。 |
| Token 存 `localStorage` | XSS 可直接读取 | 同源 HttpOnly 会话 Cookie。 |
| 多处 `catch(() => {})` | 用户不知道失败，无法恢复 | 统一 ProblemDetails、页面错误态和重试。 |

### 已确认的额外缺陷

1. `form_schema()` 没有验证用户是否被允许填写该类型。
2. `create_form_session()` 没有验证 mode、process、resource 和 TEAM_LEADER 权限。
3. `create_submission()` 接受任意 form type/values，且没有服务端字段规则校验。
4. 幂等键缺失时服务端自动生成，无法防止客户端重复提交。
5. 幂等查找没有操作者/设备作用域。
6. 班组代填仍把 session 用户作为正式员工身份，操作者与记录对象没有可靠分离。
7. 班次使用 UTC 小时推断，没有转换为 `Asia/Shanghai`。
8. `schema_version` 同时出现字符串和整数语义。
9. `/outbox` 只读空字典，Service Worker 对写 API 使用 NetworkOnly，离线记录不会自动入队。
10. 新增后端和移动端没有自动化测试。

## 2. 目标架构

```text
React Mobile UI
├─ MobileFormEngine（显示与本地即时反馈）
├─ IndexedDB drafts/outbox（离线）
└─ Mobile API client
        ↓
/api/v1/mobile（协议、Cookie、DTO、ProblemDetails）
        ↓
electronic_forms 应用模块
├─ ElectronicDefinitionService
├─ ElectronicDraftService
├─ ElectronicSubmissionService
├─ ProductionContextService
└─ MobileSessionService
        ↓
主系统 ports / repositories
├─ identity_access + employees
├─ template_versions + job_profile_versions
├─ master_data + team_memberships + resources
├─ forms + form_fields + record_versions
├─ review + audit_events
└─ tasks + exports
```

### 模块命名原则

- `mobile` 只用于 API 和前端交付适配层。
- 正式领域模块命名为 `electronic_forms`，供 PWA、微信小程序、平板和公共终端复用。
- 电子表单定义不复制纸张坐标；只保存移动端显示顺序、分组、来源、条件显隐和可编辑策略。
- 字段键、数据类型、主数据来源、数值范围和计算表达式来自已发布模板/岗位版本。

## 3. 正式数据模型

新增迁移建议使用 `alembic/versions/012_electronic_forms_ds.py`。

### 3.1 `electronic_form_definition_versions`

| 字段 | 要求 |
|---|---|
| `definition_version_id` | 字符串主键。 |
| `form_type`、`version` | 组合唯一。 |
| `status` | DRAFT/PUBLISHED/RETIRED。 |
| `template_version_id` | 关联已发布纸质模板版本。 |
| `job_profile_version_id` | 可选，关联岗位配置版本。 |
| `presentation_config` | 只保存 field_key、顺序、分组、mobile strategy、条件规则。 |
| `created_by/created_at/published_at` | 版本追溯。 |

发布规则：引用字段必须存在于目标模板；发布后不可修改；模板或岗位版本 retired 后，既有草稿仍可读取旧定义，但不能新建填报会话。

### 3.2 `electronic_drafts`

保存已联网同步的服务端草稿：owner actor、subject employee、device、definition version、values、revision、更新时间。更新必须使用 `If-Match` revision，不能覆盖其他设备的新版本。

### 3.3 `electronic_submission_receipts`

| 字段 | 用途 |
|---|---|
| `receipt_id` | 服务端提交回执。 |
| `actor_id` | 实际操作人。 |
| `subject_employee_code` | 记录归属员工；SELF 时等于 actor 对应员工。 |
| `device_id` | 公共设备追踪。 |
| `operation` | CREATE_ELECTRONIC_FORM。 |
| `client_submission_id` | 客户端稳定 UUID。 |
| `payload_hash` | 同键不同载荷时返回冲突。 |
| `form_id/record_version` | 关联主系统正式链路。 |
| `submitted_at` | 服务端时间。 |

唯一约束：`(actor_id, device_id, operation, client_submission_id)`。

### 3.4 班组与生产上下文

- 在 `MasterDataCatalog` 增加 `TEAMS`、`PRODUCTION_RESOURCES`。
- 新增 `team_memberships`，保存 employee code、team code、角色、有效期和 active。
- 资源记录使用主数据 revision 做乐观锁，笼状态变更记录审计。
- `ProductionContextService` 从班组、工单、产品、规格、当前日期和班次生成上下文；不在路由内构造固定数据。

### 3.5 移动凭据与会话

- `employee_credentials` 只保存 employee code、带盐 scrypt hash、失败次数、锁定时间和 revision；不得保存明文 PIN。
- `mobile_sessions` 保存 session token hash、actor、device、创建/到期/撤销时间；原始 token 只进入 HttpOnly Cookie。
- 登录、失败锁定、退出和会话撤销写安全审计，但审计不得包含 PIN、Cookie 或 token。

### 3.6 进入主审核链路

电子提交事务必须：

1. 创建 `forms`，模板身份来自 definition version。
2. 创建 `form_fields`，来源新增 `ELECTRONIC_SUBMITTED`。
3. 锁定值和计算值由服务端写入，忽略客户端同名值。
4. 写 `ELECTRONIC_SUBMIT` audit，记录 actor、subject、device 和 definition version。
5. 创建 receipt 并关联 form。
6. 表单进入 `NEEDS_REVIEW`，不直接生成 CONFIRMED 工资记录。
7. 继续使用现有 ReviewFacade 确认、更正、退回、作废和重导。

## 4. API 合同

保留 `/api/v1/mobile` 路径，拆分 router；不得继续使用裸 `dict[str, Any]` 作为外部合同。

### 推荐目录

```text
app/api/routers/mobile/
├─ __init__.py
├─ auth_ds.py
├─ definitions_ds.py
├─ drafts_ds.py
├─ production_ds.py
└─ submissions_ds.py
app/api/schemas/mobile_ds.py
```

### 写入规则

- 登录后使用 HttpOnly、Secure（生产）、SameSite=Strict Cookie。
- 所有写请求携带 CSRF header。
- submission 必须携带 `Idempotency-Key`，否则 400。
- submission body 必须包含 `definition_version_id`、`mode`、`subject_employee_code`、`values`、`device_id`。
- 服务端从 session 获取 actor，不接受客户端 actor_id。
- SELF 强制 subject 为本人。
- TEAM_LEADER_BATCH 要求 TEAM_LEADER 权限，并校验有效班组成员关系。
- definition version 不匹配返回 409 `SCHEMA_VERSION_CONFLICT`。
- 同一幂等键载荷不同返回 409 `IDEMPOTENCY_CONFLICT`。
- 字段错误使用 `REVIEW_RULE_BLOCKED` 风格的结构化 failures。

### 返回状态

```text
LOCAL_DRAFT      仅存在于客户端 IndexedDB
SYNCING          客户端正在提交
ACCEPTED         服务端已生成 receipt/form
NEEDS_REVIEW     已进入审核队列
CONFIRMED        审核完成
RETURNED         被退回，可产生新草稿
VOIDED           已作废
CONFLICT         版本/幂等/资源冲突
FAILED_RETRYABLE 网络或临时服务错误
FAILED_FINAL     权限或业务规则不可重试
```

## 5. 离线与 PWA 整理

### IndexedDB 数据库

使用小型、类型化的 `idb` 依赖，数据库名 `industrial-form-pwa`，至少包含：

- `drafts`：按 `owner + device + local_draft_id` 保存表单值和 definition version。
- `outbox`：保存 operation、payload、idempotency key、attempt count、next retry、last error。
- `reference_snapshots`：缓存允许离线使用的表单定义和选项，并保存 server version/etag。
- `session_metadata`：只保存非敏感显示信息；不保存 Cookie 或 PIN。

### 同步协调器

- 页面提交时先在一个 IndexedDB 事务中写 outbox，再尝试网络提交。
- 成功收到 receipt 后标记完成并删除对应 outbox payload。
- 监听 `online`，并提供“立即重试”按钮。
- 退避序列：5 秒、30 秒、2 分钟、10 分钟、30 分钟；业务冲突不自动重试。
- 同一 owner 串行发送，避免顺序相关的资源状态冲突。
- 不把 Workbox Background Sync 作为唯一机制；浏览器不支持时仍能在应用打开后同步。
- 退出登录时如果有未同步项目，必须要求“继续同步”或“明确放弃并清除”，不能静默清除。

### Service Worker 缓存边界

可以缓存：应用 shell、版本化静态资源、公开图标、带版本的非敏感表单展示配置。

禁止缓存：登录/会话、草稿、提交、审核、员工个人资料、图片证据、任何带 Authorization/Cookie 的私有响应。API 写请求保持 NetworkOnly，由应用 outbox 接管失败。

## 6. 安全边界

1. 移除源代码中的演示 PIN 和真实姓名；测试数据只放 fixtures。
2. PIN 使用带随机盐的 `hashlib.scrypt` 或组织身份提供方，不允许截断 SHA-256。
3. 登录按 employee/device/IP 限速；连续失败锁定并审计。
4. 会话服务端持久化，保存 hash 后的 session token、到期时间、设备和撤销时间。
5. Cookie 仅同源使用；生产必须 HTTPS。
6. 服务端验证每个 allowed form/process/mode/subject/resource，前端隐藏不等于权限控制。
7. 金额、数量合计、身份、班组、单价和资源状态由服务端重建。
8. 审计不记录 PIN、Cookie、完整敏感请求或密钥。
9. 公共设备需要短空闲超时、明确退出和按用户隔离 IndexedDB 数据。

## 7. 前端文件整理

### 7.1 API 与类型

把通用合同移到：

- `frontend/packages/api-client/src/mobile_ds.ts`
- `frontend/packages/api-client/src/index_ds.ts`

`frontend/apps/web/src/mobile/api.ts` 只保留 Web 环境适配，不重复 DTO。后续 OpenAPI 生成完成时替换手写类型。

### 7.2 表单引擎拆分

```text
frontend/apps/web/src/mobile/form-engine/
├─ MobileFormEngine.tsx
├─ FieldRenderer.tsx
├─ reducer.ts
├─ validation.ts
├─ computation.ts
└─ field-strategies.ts
```

- reducer 只处理状态变化。
- computation 只产生预览计算结果，并明确标注“以服务器结果为准”。
- validation 提供即时反馈，但不能代替服务端规则。
- FieldRenderer 负责七种策略的控件映射。
- 页面只负责加载 definition/context、保存草稿和提交，不再硬编码字段。

### 7.3 页面去硬编码

- `MobileBambooProcessPage` 从 definition 和 active resources 构建步骤。
- `MobileSheetPiecePage` 与 `MobileTeamSheetPiecePage` 复用相同引擎和 submission coordinator。
- 班组成员从 API 获取，不在 TS 文件写张三/李四。
- Drafts/Outbox 读取 IndexedDB；Submissions 读取服务端 receipts/forms。
- 所有空 `catch` 改成可见错误、重试或登录失效跳转。

## 8. 分阶段实施任务

### Task 1：锁定原型行为并建立安全测试网

**Files:**
- Create: `tests/api/test_mobile_pilot_contract_ds.py`
- Create: `frontend/apps/web/src/mobile/mobile-routes.test.tsx`
- Create: `frontend/apps/web/src/mobile/form-engine.test.tsx`
- Read only: 当前 `mobile_ds.py`、`MobileFormEngine.tsx` 和三个表单页面

- [ ] 为登录、可用表单、表单会话、草稿、提交和列表记录当前行为测试。
- [ ] 增加明确失败测试：无权限 form type、非法 mode、伪造 subject、缺幂等键、同键不同 payload。
- [ ] 为七种字段策略、条件显隐和计算预览建立前端测试。
- [ ] 运行测试，确认当前正向行为通过、安全测试失败。
- [ ] Commit: `test(mobile): capture pilot behavior and security gaps`

Commands:

```text
uv run pytest tests/api/test_mobile_pilot_contract_ds.py -q
npm run test -w @form-detection/web -- src/mobile/mobile-routes.test.tsx src/mobile/form-engine.test.tsx
```

### Task 2：建立电子表单领域模型与迁移

**Files:**
- Create: `app/modules/electronic_forms/models_ds.py`
- Create: `app/modules/electronic_forms/ports_ds.py`
- Create: `app/modules/electronic_forms/facade_ds.py`
- Create: `app/adapters/database/electronic_forms_repository_ds.py`
- Create: `alembic/versions/012_electronic_forms_ds.py`
- Modify: `app/adapters/database/models.py`
- Modify: `app/domain/models.py`（增加 `ELECTRONIC_SUBMITTED` value source）
- Test: `tests/modules/test_electronic_forms_ds.py`
- Test: `tests/integration/test_electronic_forms_repository_ds.py`

- [ ] 先写 definition 不可变、draft revision、receipt 幂等和 payload conflict 测试。
- [ ] 添加 definition/draft/receipt/session/team membership 数据模型和数据库行模型。
- [ ] 实现 SQLAlchemy repository，所有写操作使用事务。
- [ ] 执行 011 → 012 升级和空库建库测试。
- [ ] Commit: `feat(electronic-forms): add persistent definitions drafts and receipts`

Commands:

```text
uv run pytest tests/modules/test_electronic_forms_ds.py tests/integration/test_electronic_forms_repository_ds.py -q
uv run pytest tests/integration/test_migrations_backup_integrity_ds.py -q
```

### Task 3：把电子定义绑定主模板和岗位版本

**Files:**
- Modify: `app/modules/electronic_forms/facade_ds.py`
- Modify: `app/adapters/database/template_repository_ds.py`（只增加所需读取接口）
- Create: `app/application/electronic_definitions_ds.py`
- Create: `app/api/schemas/mobile_ds.py`
- Create: `app/api/routers/mobile/definitions_ds.py`
- Test: `tests/api/test_mobile_definitions_ds.py`

- [ ] 测试只能发布引用已发布模板/岗位版本的定义。
- [ ] 测试 presentation field_key 必须存在，且不得覆盖数据类型和正式规则。
- [ ] 用受控 seed 建立三种原型定义；名称必须与业务正式名称一致后才能标记 PUBLISHED。
- [ ] available forms 必须按 actor role、allowed process 和 definition status 过滤。
- [ ] Commit: `feat(mobile): serve versioned electronic form definitions`

特别门槛：当前“竹丝工序记录”不能自动视为“竹丝装笼跟踪牌”；当前“配片工作记录/班组配片记录”也不能自动视为“配片数计量考核表”。字段、填写责任和审核顺序必须以正式业务定义为准。

### Task 4：接入身份、班组和生产上下文

**Files:**
- Create: `app/application/mobile_identity_ds.py`
- Create: `app/application/production_context_ds.py`
- Create: `app/api/routers/mobile/auth_ds.py`
- Create: `app/api/routers/mobile/production_ds.py`
- Modify: `app/modules/master_data/models_ds.py`
- Modify: `app/modules/master_data/facade_ds.py`
- Test: `tests/api/test_mobile_identity_ds.py`
- Test: `tests/application/test_production_context_ds.py`

- [ ] 用 employee catalog 查身份，不再维护 `_users`。
- [ ] 持久化凭据/会话，使用 scrypt 盐和会话 token hash。
- [ ] 增加登录限速、失败锁定、撤销和到期测试。
- [ ] 建立 team membership 和 production resource 查询。
- [ ] 全部时间通过 `ZoneInfo("Asia/Shanghai")` 生成业务日期/班次。
- [ ] 校验 TEAM_LEADER 只能选择有效期内本班组员工。
- [ ] Commit: `feat(mobile): integrate identity teams and production context`

### Task 5：正式提交进入主审核链路

**Files:**
- Create: `app/application/electronic_submissions_ds.py`
- Create: `app/api/routers/mobile/submissions_ds.py`
- Modify: `app/services/container.py`
- Modify: `app/adapters/database/repositories.py`（复用/补充原子创建入口）
- Test: `tests/application/test_electronic_submissions_ds.py`
- Test: `tests/api/test_mobile_submissions_ds.py`
- Test: `tests/integration/test_mobile_review_export_loop_ds.py`

- [ ] 写失败测试：伪造身份、越权 mode、未知字段、计算字段篡改、过期 definition、资源 revision 冲突。
- [ ] 写幂等并发测试：同键同 payload 返回同 receipt；同键不同 payload 返回 409。
- [ ] 服务端重建 identity/default/computed 值并执行模板/主数据规则。
- [ ] 原子创建 form、fields、audit 和 receipt，状态进入 NEEDS_REVIEW。
- [ ] 验证工作台能打开无纸质图片的电子表单，完成确认、更正和导出。
- [ ] Commit: `feat(mobile): submit electronic forms into review workflow`

### Task 6：实现 IndexedDB 草稿和真实 Outbox

**Files:**
- Modify: `frontend/apps/web/package.json`（增加 `idb`）
- Create: `frontend/apps/web/src/mobile/storage/db.ts`
- Create: `frontend/apps/web/src/mobile/storage/drafts.ts`
- Create: `frontend/apps/web/src/mobile/storage/outbox.ts`
- Create: `frontend/apps/web/src/mobile/sync/SubmissionCoordinator.ts`
- Create: `frontend/apps/web/src/mobile/sync/useOutboxSync.ts`
- Modify: `MobileDraftsPage.tsx`、`MobileOutboxPage.tsx`、各填报页面
- Test: `frontend/apps/web/src/mobile/storage/offline.test.ts`
- Test: `frontend/apps/web/src/mobile/sync/submission-coordinator.test.ts`

- [ ] 先写断网保存、刷新恢复、重复同步、冲突停止和指数退避测试。
- [ ] 实现每用户/设备隔离的 IndexedDB stores。
- [ ] 提交先写 outbox，再尝试 API；receipt 成功后清理。
- [ ] online 事件和手动重试共用同一 coordinator。
- [ ] 移除服务端 `/outbox` 和 `_outbox`。
- [ ] Commit: `feat(pwa): add durable offline drafts and submission outbox`

### Task 7：拆分表单引擎并统一错误处理

**Files:**
- Create: `frontend/apps/web/src/mobile/form-engine/*`
- Create: `frontend/apps/web/src/mobile/MobileProblemNotice.tsx`
- Modify: `frontend/apps/web/src/mobile/api.ts`
- Modify: 所有 `Mobile*Page.tsx`
- Create: `frontend/packages/api-client/src/mobile_ds.ts`
- Modify: `frontend/packages/api-client/src/index_ds.ts`
- Test: form engine、错误映射和页面恢复测试

- [ ] 把 reducer、条件、计算、校验和控件渲染拆成纯模块。
- [ ] 页面只接收 definition/context，不再重复字段定义。
- [ ] 移除所有空 catch；401、403、409、422、5xx 和网络错误有不同恢复操作。
- [ ] Token 改为 HttpOnly Cookie，fetch 使用 `credentials: "include"`。
- [ ] Commit: `refactor(mobile): split form engine and expose recoverable errors`

### Task 8：收紧 Service Worker 和公共设备行为

**Files:**
- Modify: `frontend/apps/web/vite.config.ts`
- Modify: `frontend/apps/web/src/pwa/register-sw.ts`
- Modify: `frontend/apps/web/src/pwa/update-notice.tsx`
- Modify: `MobileProfilePage.tsx`、`MobileLayout.tsx`
- Test: `frontend/apps/web/src/pwa/pwa-policy.test.ts`
- Add E2E: `frontend/apps/web/e2e/mobile-offline.spec.ts`

- [ ] 测试私有 API、图片、登录和提交不进入 Cache Storage。
- [ ] 测试新版本提示不会在用户填写中强制刷新。
- [ ] 测试公共设备退出时对未同步 outbox 给出明确选择。
- [ ] 测试应用更新后 IndexedDB schema 可迁移且草稿不丢失。
- [ ] Commit: `fix(pwa): protect private data and safe application updates`

### Task 9：停止原型状态接线并完成验收

**Files:**
- Replace routing content: `app/api/routers/mobile_ds.py` 改为新 routers 聚合，不再注册 module-level stores/seed；原实现保留在 Git 历史中供追溯。
- Modify: `app/api/main_ds.py`
- Update: `docs/PROJECT_TECHNICAL_OVERVIEW.md`
- Create: `docs/PWA_MOBILE_ACCEPTANCE_CHECKLIST.md`

- [ ] 搜索并确认生产代码不含 `1234`、张三/李四、`_submissions`、`_drafts`、`_outbox` 和固定笼号。
- [ ] Python 全量测试、Ruff、mypy 通过。
- [ ] 前端测试、typecheck、production build 通过。
- [ ] Playwright 覆盖登录、SELF、TEAM_LEADER_BATCH、断网、重复提交、冲突、审核和导出。
- [ ] 真机验证 Android/iOS 安装、更新、弱网、横竖屏和公共设备退出。
- [ ] 独立提交文档与验收结果。
- [ ] Commit: `docs(pwa): record electronic filing acceptance`

Final commands:

```text
uv run pytest -q -p no:cacheprovider
uv run ruff check app config tests --no-cache
uv run mypy app config
cd frontend
npm test
npm run build:web
```

## 9. 合并到 `modular-architecture` 的硬门槛

以下全部满足前不得快进主线：

- [ ] 后端不存在 module-level 可变业务存储。
- [ ] 演示用户、PIN、成员、笼号、工单和产品已移出生产代码。
- [ ] 正式提交进入现有审核、审计和导出链路。
- [ ] 服务端拥有最终身份、权限、规则和计算权威。
- [ ] 数据库幂等并发测试通过。
- [ ] 离线草稿与 outbox 在刷新、重启和断网恢复后不丢失。
- [ ] Service Worker 不缓存私有响应。
- [ ] 两张正式业务表的字段、责任和审核顺序已落实为已发布 definition version。
- [ ] Python 与前端全量检查通过。
- [ ] 移动端真机与人工业务验收通过。
- [ ] `modular-architecture` 工作树现有未提交内容已被安全保存并确认归属。

## 10. 明确不在本轮整理中扩张的范围

- 不实现完整工资规则引擎；电子提交只进入审核，正式工资仍按主系统后续规则阶段推进。
- 不同时开发微信小程序；只保持 API 和 TypeScript 纯类型可复用。
- 不引入微服务、消息中间件或 Kubernetes。
- 不让 AI 修改表单定义、提交值或工资数据。
- 不把模板设计器搬到手机端。
- 不在未完成认证、HTTPS 和存储迁移前宣称支持约 500 人生产使用。

## 11. 完成后的预期结果

整理完成后，现有原型中有价值的移动体验会保留，但数据只有一条正式路径：

```text
电子填报或纸质识别
→ 同一模板/岗位字段身份
→ 同一主数据和规则校验
→ 同一审核队列
→ 同一记录版本与审计
→ 同一导出和重导机制
```

PWA 可以安装、离线保存和可靠补交；服务重启不会丢失正式数据；班组长代填、重复提交、规则冲突和更正均可追溯。此时才适合把 `codex/low-token-ui-v2` 快进合并到正式主线 `modular-architecture`。
