# PWA 移动端生产接线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把现有移动端页面、IndexedDB 离线底座和 PWA 外壳接入正式电子表单领域服务，移除内存用户与硬编码生产数据，使电子提交可靠进入主系统审核、审计和导出链路。

**Architecture:** `/api/v1/mobile` 只承担移动协议、Cookie 会话、DTO 和错误映射；身份、定义、草稿、生产上下文和提交由应用服务处理。正式提交使用单一 SQLAlchemy 事务同时写入 `forms`、`form_fields`、`audit_events` 和 `electronic_submission_receipts`；浏览器使用 IndexedDB 保存草稿与 outbox，联网时通过幂等键补交。

**Tech Stack:** Python 3.11、FastAPI、Pydantic 2、SQLAlchemy 2、Alembic、React 18、TypeScript、Vite、vite-plugin-pwa、IndexedDB/idb、pytest、Vitest。

---

## 0. 执行基线和边界

### 0.1 当前分支

- 只在现有 `codex/low-token-ui-v2` 分支继续开发，不创建新分支。
- 当前基线为 `8db5302 feat(pwa): add durable offline drafts and submission outbox`。
- 当前分支相对 `574dea0` 有 5 个已提交变更。
- 工作树中旧 PWA 页面、旧 `mobile_ds.py`、PWA 配置和样式仍未提交。实施前必须先确认这些文件归属，不得使用 reset、checkout 或清理命令丢弃。
- 全部硬门槛通过后，才允许将验收提交快进到正式主线 `modular-architecture`。

### 0.2 已完成且不重复开发

- `electronic_forms` 的 Definition、Draft、Receipt 领域对象及 012 迁移。
- 电子定义与已发布模板字段键的绑定校验。
- `ValueSource.ELECTRONIC_SUBMITTED`。
- IndexedDB 的 drafts、outbox、referenceSnapshots、sessionMetadata 四类存储骨架。
- SubmissionCoordinator 的“先入队、再尝试提交”基本方向。
- 现有原型页面的布局、路由、七类字段呈现策略和 PWA 安装外壳。
- 已提交测试只作为回归基线；没有修改相关模块时不重复进行人工验收。

### 0.3 当前代码中必须纠正的状态

以下结论以当前代码为准，不能继续写成“已经生产化”：

1. `app/application/mobile_identity_ds.py` 仍使用 `_PILOT_USERS`、`_SESSIONS`、固定演示 PIN 和截断 SHA-256；尚未接入数据库身份。
2. `app/services/container.py` 尚未注册电子定义、草稿、回执、移动身份和电子提交服务。
3. `app/api/routers/mobile_ds.py` 仍是 module-level 内存路由，包含硬编码用户、模板、班组、笼号、工单和产品。
4. `ElectronicFormIntegration` 当前分别调用 FormCreator 和 ReceiptRepository；现有 SQLAlchemy 实现没有证明四类记录在同一事务提交。
5. 前端页面继续调用 `frontend/apps/web/src/mobile/api.ts` 的旧接口，身份 Token 保存在 `localStorage`。
6. `SubmissionCoordinator` 尚未被页面使用；`MobileOutboxPage` 仍读取旧服务端 `/outbox`。
7. `idb` 已写入 `frontend/apps/web/package.json`，但必须通过一次受控安装让 lockfile 与 `^8.0.0` 一致。
8. Service Worker 对大多数 API 使用 `NetworkOnly`，但缓存白名单、退出清理和升级行为尚未形成自动化安全验收。

### 0.4 本阶段不做

- 不开发微信小程序。
- 不开发移动端模板设计器。
- 不新增 AI 执行权限。
- 不实现完整工资规则引擎。
- 不用硬编码数据伪装生产资源；主系统没有的数据必须明确返回“暂不可用”。
- 不重复纸张打印、OCR、Excel、审核工作台和既有模板的完整验收。

## 1. 目标请求闭环

```text
移动端登录
→ HttpOnly 同源会话
→ 查询已授权的已发布电子定义
→ 查询主数据生产上下文
→ IndexedDB 保存草稿
→ outbox 生成 client_submission_id
→ 服务端重新校验身份、对象、字段和计算
→ 单事务写 Form + FormField + Audit + Receipt
→ Form 进入 NEEDS_REVIEW
→ 现有工作台审核
→ 现有记录版本、导出与重导
```

服务端是身份、权限、字段规则、计算结果和提交状态的最终权威。浏览器计算只用于即时预览，不能直接成为正式金额或身份事实。

## 2. 文件责任边界

| 文件或目录 | 单一职责 |
|---|---|
| `app/infrastructure/database/electronic_submission_uow_ds.py` | 为 Form、Field、Audit、Receipt 提供一个事务边界。 |
| `app/application/mobile_identity_ds.py` | 验证 PIN、签发/验证/撤销数据库会话；不保存演示用户。 |
| `app/api/routers/mobile_auth_ds.py` | 登录、会话、退出和 Cookie。 |
| `app/api/routers/mobile_definitions_ds.py` | 可填写定义、定义详情和只读选项。 |
| `app/api/routers/mobile_context_ds.py` | 员工、班组、工单、产品、工序和资源上下文。 |
| `app/api/routers/mobile_submissions_ds.py` | 草稿、提交回执和提交记录。 |
| `app/api/routers/mobile_ds.py` | 只聚合上述路由，不保存业务状态。 |
| `frontend/packages/api-client/src/mobile_ds.ts` | 移动 API 的唯一 TypeScript 契约。 |
| `frontend/apps/web/src/mobile/session/` | 浏览器会话状态和路由保护。 |
| `frontend/apps/web/src/mobile/storage/` | IndexedDB 草稿、outbox、参考快照和退出清理。 |
| `frontend/apps/web/src/mobile/sync/` | 队列提交、重试、冲突和在线恢复。 |
| `frontend/apps/web/src/mobile/form-engine/` | reducer、校验、计算和字段渲染。 |

## 3. 分阶段任务

### Task 1：把电子提交改为真正的单事务

**Files:**
- Create: `app/infrastructure/database/electronic_submission_uow_ds.py`
- Modify: `app/application/electronic_submissions_ds.py`
- Modify: `app/adapters/database/electronic_forms_repository_ds.py`
- Test: `tests/application/test_electronic_submissions_ds.py`
- Test: `tests/integration/test_electronic_submission_transaction_ds.py`

- [ ] **Step 1：先写事务回滚测试**

测试必须证明：Receipt 写入失败时，Form、FormField 和 Audit 均不存在；Form 写入失败时 Receipt 也不存在。

```python
def test_receipt_failure_rolls_back_form_fields_and_audit(
    failing_receipt_uow_factory,
    query_repository,
):
    integration = ElectronicFormIntegration(
        uow_factory=failing_receipt_uow_factory,
    )
    with pytest.raises(RuntimeError, match="receipt write failed"):
        integration.accept(valid_electronic_command())
    assert query_repository.list_forms() == []
    assert query_repository.list_audits() == []
    assert query_repository.list_receipts() == []
```

- [ ] **Step 2：运行测试并确认先失败**

Run: `uv run pytest tests/integration/test_electronic_submission_transaction_ds.py -q -p no:cacheprovider`

Expected: FAIL，因为当前 FormCreator 与 ReceiptRepository 不共享提交边界。

- [ ] **Step 3：建立统一 UoW**

接口必须由同一个 SQLAlchemy Session 暴露表单和回执仓储：

```python
class ElectronicSubmissionUnitOfWork(Protocol):
    forms: SqlAlchemyFormRepository
    receipts: SqlAlchemyElectronicSubmissionReceiptRepository
    session: Session

    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None: ...
```

`ElectronicFormIntegration.accept()` 只能在 `with self._uow_factory() as uow:` 内完成幂等查询，并通过 `uow.forms.add_form()`、`add_form_field()`、`add_audit_event()` 和 `uow.receipts.add()` 写入。禁止在服务内创建第二个 Session 或手工提前 commit。

- [ ] **Step 4：覆盖并发幂等**

同一 `actor_id + device_id + operation + client_submission_id`：

- 相同 payload 返回同一 Receipt；
- 不同 payload 返回 `409 IDEMPOTENCY_CONFLICT`；
- 两个并发请求最终只能有一条 Form 和一条 Receipt。

- [ ] **Step 5：运行局部测试**

Run: `uv run pytest tests/application/test_electronic_submissions_ds.py tests/integration/test_electronic_submission_transaction_ds.py tests/integration/test_electronic_forms_repository_ds.py -q -p no:cacheprovider`

Expected: PASS。

- [ ] **Step 6：提交**

```text
git add app/infrastructure/database/electronic_submission_uow_ds.py app/application/electronic_submissions_ds.py app/adapters/database/electronic_forms_repository_ds.py tests/application/test_electronic_submissions_ds.py tests/integration/test_electronic_submission_transaction_ds.py
git commit -m "fix(mobile): make electronic submission atomic"
```

### Task 2：用数据库身份和会话替换试点用户

**Files:**
- Create: `alembic/versions/013_mobile_identity_ds.py`
- Modify: `app/adapters/database/models.py`
- Create: `app/adapters/database/mobile_identity_repository_ds.py`
- Modify: `app/application/mobile_identity_ds.py`
- Modify: `app/infrastructure/database/migrations.py`
- Test: `tests/application/test_mobile_identity_ds.py`
- Test: `tests/integration/test_mobile_identity_repository_ds.py`
- Modify test: `tests/integration/test_migrations_backup_integrity_ds.py`

- [ ] **Step 1：写失败测试**

覆盖有效员工、停用员工、错误 PIN、连续失败锁定、会话过期、撤销会话和服务重启后会话仍可验证。测试数据必须由 fixture 创建，不得在生产代码 seed 演示工人。

```python
def test_authentication_uses_active_employee_and_persistent_credential(
    identity_service, employee_factory, credential_factory
):
    employee_factory(code="E10001", active=True)
    credential_factory(code="E10001", pin="2468")
    actor, token = identity_service.authenticate("E10001", "2468", "device-a")
    assert actor.employee_code == "E10001"
    assert identity_service.verify_session(token).employee_code == "E10001"
```

- [ ] **Step 2：新增追加式迁移**

013 只新增：

- `mobile_credentials(employee_catalog, employee_code, pin_salt, pin_hash, failed_attempts, locked_until, revision, updated_at)`；
- `mobile_sessions(session_id PK, employee_catalog, employee_code, device_id, token_hash UNIQUE, expires_at, revoked_at, created_at)`；
- `mobile_access_profiles(employee_catalog, employee_code, team_id, team_name, position, roles JSON, allowed_form_types JSON, allowed_processes JSON, active)`。

`employee_catalog` 固定为 `EMPLOYEE`，三张表使用 `(employee_catalog, employee_code)` 对应现有 `master_data_records(catalog, code)` 复合身份；禁止假设 `employee_code` 单列是现有表的独立主键。

PIN 使用随机 salt 的 `hashlib.scrypt`；数据库只保存 token hash，不保存明文 PIN 或明文会话 Token。

- [ ] **Step 3：替换试点函数**

从 `mobile_identity_ds.py` 删除 `_PILOT_USERS`、`_SESSIONS`、`_pilot_lookup()`、`_pilot_session_get()`、`_pilot_session_delete()` 和截断 SHA-256。应用服务只依赖仓储端口与 clock。

- [ ] **Step 4：运行身份和迁移测试**

Run: `uv run pytest tests/application/test_mobile_identity_ds.py tests/integration/test_mobile_identity_repository_ds.py tests/integration/test_migrations_backup_integrity_ds.py -q -p no:cacheprovider`

Expected: PASS；从 012 升级到 013 后旧表单、电子定义、草稿和回执仍存在。

- [ ] **Step 5：静态检查并提交**

Run: `uv run ruff check app/application/mobile_identity_ds.py app/adapters/database/mobile_identity_repository_ds.py alembic/versions/013_mobile_identity_ds.py tests/application/test_mobile_identity_ds.py tests/integration/test_mobile_identity_repository_ds.py --no-cache`

```text
git add alembic/versions/013_mobile_identity_ds.py app/adapters/database/models.py app/adapters/database/mobile_identity_repository_ds.py app/application/mobile_identity_ds.py app/infrastructure/database/migrations.py tests/application/test_mobile_identity_ds.py tests/integration/test_mobile_identity_repository_ds.py tests/integration/test_migrations_backup_integrity_ds.py
git commit -m "feat(mobile): persist credentials and sessions"
```

### Task 3：建立正式移动 API 并注册到组合根

**Files:**
- Modify: `app/services/container.py`
- Replace: `app/api/routers/mobile_ds.py`
- Create: `app/api/routers/mobile_auth_ds.py`
- Create: `app/api/routers/mobile_definitions_ds.py`
- Create: `app/api/routers/mobile_context_ds.py`
- Create: `app/api/routers/mobile_submissions_ds.py`
- Modify: `app/api/schemas/mobile_ds.py`
- Test: `tests/api/test_mobile_auth_ds.py`
- Modify test: `tests/api/test_mobile_definitions_ds.py`
- Create: `tests/api/test_mobile_submissions_ds.py`
- Create: `tests/api/test_mobile_context_ds.py`

- [ ] **Step 1：先写组合根和路由失败测试**

测试必须通过真实 `Services` 构建应用，并证明 `mobile_ds.py` 不再暴露 `_users`、`_sessions`、`_form_schemas`、`_drafts`、`_submissions` 或 `_outbox`。

```python
def test_mobile_router_has_no_process_local_business_store():
    import app.api.routers.mobile_ds as mobile
    forbidden = {"_users", "_sessions", "_form_schemas", "_drafts", "_submissions", "_outbox"}
    assert forbidden.isdisjoint(vars(mobile))
```

- [ ] **Step 2：注册正式服务**

`Services` 增加电子定义、草稿、身份和电子提交服务。`build_services()` 必须通过受控 Session/UoW 工厂构造它们；路由只从 `request.app.state.services` 取服务。

- [ ] **Step 3：实现 Cookie 会话边界**

- 登录成功设置 `HttpOnly`、`SameSite=Lax` Cookie；生产 HTTPS 时设置 `Secure`。
- `LoginResponse` 不再返回 token。
- 退出撤销服务端会话并清除 Cookie。
- 所有写请求验证同源/CSRF；不得接受 URL 中的 Token。
- 审计和日志不得记录 PIN、Cookie、Authorization 或完整提交值。

- [ ] **Step 4：定义与上下文必须来自正式数据**

- `/available-forms` 只返回操作者允许且状态为 PUBLISHED 的 DefinitionVersion。
- `/form-schemas/{form_type}` 必须同时检查授权和 definition version。
- 员工、工单、产品、工序从现有主数据读取。
- 当前主系统没有正式“笼资源”数据时，竹丝资源接口返回结构化 `RESOURCE_PROVIDER_UNAVAILABLE`，对应表单从可填写列表隐藏；禁止保留固定笼号。
- 班组长代填对象必须来自有效员工与授权班组关系，不能信任请求中的姓名和班组。

- [ ] **Step 5：提交端点重新构造命令**

服务端从 Cookie Actor、已发布 Definition、主数据和模板绑定重建 `ElectronicFormCommand`。客户端只能提交 `definition_version_id`、`mode`、`subject_employee_code`、`device_id`、`values`；不得自行指定 template ID、姓名、班组或计算结果。

- [ ] **Step 6：统一错误映射**

使用现有 ProblemDetails：401 会话失效、403 无权填报、409 幂等/版本冲突、422 字段规则错误、503 生产资源暂不可用。工作人员消息使用中文，技术 code 保留用于前端分支处理。

- [ ] **Step 7：运行 API 定向测试并提交**

Run: `uv run pytest tests/api/test_mobile_auth_ds.py tests/api/test_mobile_definitions_ds.py tests/api/test_mobile_context_ds.py tests/api/test_mobile_submissions_ds.py -q -p no:cacheprovider`

Expected: PASS。

```text
git add app/services/container.py app/api/routers/mobile_ds.py app/api/routers/mobile_auth_ds.py app/api/routers/mobile_definitions_ds.py app/api/routers/mobile_context_ds.py app/api/routers/mobile_submissions_ds.py app/api/schemas/mobile_ds.py tests/api/test_mobile_auth_ds.py tests/api/test_mobile_definitions_ds.py tests/api/test_mobile_context_ds.py tests/api/test_mobile_submissions_ds.py
git commit -m "feat(mobile): route PWA through production services"
```

### Task 4：建立唯一前端 API 客户端与会话守卫

**Files:**
- Create: `frontend/packages/api-client/src/mobile_ds.ts`
- Modify: `frontend/packages/api-client/src/index_ds.ts`
- Replace: `frontend/apps/web/src/mobile/api.ts`
- Replace: `frontend/apps/web/src/mobile/auth.ts`
- Create: `frontend/apps/web/src/mobile/session/MobileSessionProvider.tsx`
- Create: `frontend/apps/web/src/mobile/session/RequireMobileSession.tsx`
- Modify: `frontend/apps/web/src/app/router.tsx`
- Test: `frontend/packages/api-client/src/mobile_ds.test.ts`
- Test: `frontend/apps/web/src/mobile/session/mobile-session.test.tsx`

- [ ] **Step 1：安装并锁定依赖**

Run: `cd frontend && npm install`

Expected: `frontend/package-lock.json` 中 web workspace 的直接依赖解析到满足 `idb ^8.0.0` 的版本；不得手工编辑 lockfile。

- [ ] **Step 2：写失败测试**

API 测试断言所有请求使用 `credentials: "same-origin"`，登录结果不含 token；路由测试断言未登录访问 `/mobile/home` 自动跳到 `/mobile/login`，会话失效时保留安全的返回路径。

- [ ] **Step 3：建立共享客户端**

```ts
export interface MobileProblem {
  title: string;
  status: number;
  code: string;
  detail: string;
  request_id: string;
}

export class MobileApiClient {
  constructor(private readonly baseUrl = "/api/v1/mobile") {}

  private request(path: string, init: RequestInit = {}) {
    return fetch(`${this.baseUrl}${path}`, {
      ...init,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", ...init.headers },
    });
  }
}
```

所有页面只从 `@form-detection/api-client` 使用移动契约。旧 `mobile/api.ts` 最终删除或只做零逻辑 re-export；`auth.ts` 不再读写 `localStorage` Token。

- [ ] **Step 4：建立会话 Provider 和守卫**

Provider 状态固定为 `loading | authenticated | anonymous | error`。禁止在未确认 session 时闪现业务页面；401 清除 sessionMetadata 并跳转登录。

- [ ] **Step 5：局部验证并提交**

Run: `cd frontend && npm test -w @form-detection/api-client -- mobile_ds.test.ts && npm test -w @form-detection/web -- mobile-session.test.tsx mobile-routes.test.tsx && npm run typecheck -w @form-detection/web`

Expected: PASS。

```text
git add frontend/package-lock.json frontend/packages/api-client/src/mobile_ds.ts frontend/packages/api-client/src/mobile_ds.test.ts frontend/packages/api-client/src/index_ds.ts frontend/apps/web/src/mobile/api.ts frontend/apps/web/src/mobile/auth.ts frontend/apps/web/src/mobile/session frontend/apps/web/src/app/router.tsx
git commit -m "feat(mobile): use typed cookie session client"
```

### Task 5：把移动页面接入定义、主数据、IndexedDB 和 outbox

**Files:**
- Modify: `frontend/apps/web/src/mobile/MobileHomePage.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileRecordPage.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileBambooProcessPage.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileSheetPiecePage.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileTeamSheetPiecePage.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileDraftsPage.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileOutboxPage.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileSubmissionsPage.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileProfilePage.tsx`
- Modify: `frontend/apps/web/src/mobile/storage/drafts.ts`
- Modify: `frontend/apps/web/src/mobile/storage/outbox.ts`
- Modify: `frontend/apps/web/src/mobile/sync/SubmissionCoordinator.ts`
- Create: `frontend/apps/web/src/mobile/sync/submission-coordinator.test.ts`
- Create: `frontend/apps/web/src/mobile/mobile-production-flow.test.tsx`

- [ ] **Step 1：写页面换轨失败测试**

覆盖：已发布定义加载、离线草稿刷新后恢复、班组长选择有效成员、提交先进入 outbox、相同 idempotency key 补交、成功回执删除 outbox、422 最终失败保留可查看原因。

- [ ] **Step 2：统一页面加载模型**

页面只能展示 API 返回的定义与上下文：

- Home/Record：来自 `available-forms`；
- Sheet/Team：来自 Definition + production context；
- Bamboo：只有资源 provider 可用时展示；
- Team：成员来自服务端，不允许组件内硬编码姓名；
- Submissions：展示 Receipt 状态和关联 Form；
- Drafts/Outbox：直接读取 IndexedDB，不请求旧服务端列表。

- [ ] **Step 3：修正草稿主键语义**

IndexedDB `drafts` 的 keyPath 与 TypeScript 注释保持一致。建议显式增加 `storageKey`，不要把调用方的 `localDraftId` 原地改写：

```ts
interface StoredDraft extends LocalDraft {
  storageKey: string;
}
```

删除单条草稿时使用 owner/device/localDraftId 重新生成 storageKey，确保公共设备不同工人的草稿不会互相删除。

- [ ] **Step 4：修正同步状态机**

- 导出公开 `flushPendingOutbox()`，登录成功和 `online` 事件均调用；
- `_syncing` 改为共享 Promise，禁止递归等待；
- 401 暂停同步并要求登录；
- 409 幂等冲突保留为 `FAILED_FINAL`，不能静默删除；
- 422/403 进入 `FAILED_FINAL` 并显示中文原因；
- 网络异常和 5xx 才指数退避；
- 服务端成功回执后删除 outbox，并删除对应草稿；
- outbox 页面提供“重试”和“删除未提交记录”，删除必须二次确认。

- [ ] **Step 5：删除静默错误**

移除业务页面中的空 `catch(() => {})`。每个失败状态必须至少提供：中文说明、重试按钮、请求编号（收进追溯详情）。

- [ ] **Step 6：运行定向测试并提交**

Run: `cd frontend && npm test -w @form-detection/web -- submission-coordinator.test.ts mobile-production-flow.test.tsx mobile-routes.test.tsx && npm run typecheck -w @form-detection/web`

Expected: PASS。

```text
git add frontend/apps/web/src/mobile
git commit -m "feat(mobile): connect pages to durable submission flow"
```

### Task 6：拆分 MobileFormEngine，保持业务行为不变

**Files:**
- Replace: `frontend/apps/web/src/mobile/MobileFormEngine.tsx`
- Create: `frontend/apps/web/src/mobile/form-engine/types.ts`
- Create: `frontend/apps/web/src/mobile/form-engine/reducer.ts`
- Create: `frontend/apps/web/src/mobile/form-engine/validation.ts`
- Create: `frontend/apps/web/src/mobile/form-engine/computation.ts`
- Create: `frontend/apps/web/src/mobile/form-engine/FieldRenderer.tsx`
- Create: `frontend/apps/web/src/mobile/form-engine/MobileFormEngine.tsx`
- Modify test: `frontend/apps/web/src/mobile/form-engine.test.tsx`
- Create test: `frontend/apps/web/src/mobile/form-engine/reducer.test.ts`
- Create test: `frontend/apps/web/src/mobile/form-engine/validation.test.ts`

- [ ] **Step 1：把当前 30 项行为测试作为黑盒护栏**

先运行现有测试并记录摘要，不改断言语义：

Run: `cd frontend && npm test -w @form-detection/web -- form-engine.test.tsx`

Expected: 当前基线 PASS；若失败，先停止拆分并记录真实失败，不允许通过删除断言继续。

- [ ] **Step 2：先抽取纯类型和 reducer**

`reducer.ts` 只处理字段值、touched、step、submit/draft 状态；不得发 API 请求或读取浏览器存储。

- [ ] **Step 3：抽取服务端一致的校验与计算预览**

`validation.ts` 接受 Definition 和 values 返回稳定错误数组；`computation.ts` 只计算显示预览。提交前仍以服务端返回为准。

- [ ] **Step 4：抽取 FieldRenderer**

七类字段策略各自使用明确 props；条件显隐字段隐藏时清除不允许提交的旧值。无障碍标签、数字键盘提示和错误关联保持可测试。

- [ ] **Step 5：保留兼容入口**

旧 `MobileFormEngine.tsx` 只 re-export 新入口，待所有 import 更新后再删除，避免一次提交同时改动所有页面。

- [ ] **Step 6：运行测试并提交**

Run: `cd frontend && npm test -w @form-detection/web -- form-engine.test.tsx reducer.test.ts validation.test.ts && npm run typecheck -w @form-detection/web`

Expected: 原行为测试与新增纯函数测试全部 PASS。

```text
git add frontend/apps/web/src/mobile/MobileFormEngine.tsx frontend/apps/web/src/mobile/form-engine frontend/apps/web/src/mobile/form-engine.test.tsx
git commit -m "refactor(mobile): split form engine responsibilities"
```

### Task 7：收紧 Service Worker、更新和公共设备退出

**Files:**
- Modify: `frontend/apps/web/vite.config.ts`
- Modify: `frontend/apps/web/src/pwa/register-sw.ts`
- Modify: `frontend/apps/web/src/pwa/update-notice.tsx`
- Modify: `frontend/apps/web/src/mobile/MobileProfilePage.tsx`
- Modify: `frontend/apps/web/src/mobile/storage/db.ts`
- Create: `frontend/apps/web/src/mobile/storage/session-cleanup.ts`
- Create test: `frontend/apps/web/src/pwa/pwa-cache-policy.test.ts`
- Create test: `frontend/apps/web/src/mobile/storage/session-cleanup.test.ts`

- [ ] **Step 1：写缓存策略静态测试**

测试必须证明以下路径不使用 CacheFirst、NetworkFirst 或 StaleWhileRevalidate：

- `/api/v1/mobile/auth/*`
- `/api/v1/mobile/submissions*`
- `/api/v1/mobile/drafts*`
- `/api/v1/mobile/context*`
- `/api/v1/mobile/active-resources*`
- 所有证据图片和下载文件。

允许缓存的只读参考数据必须不含姓名、工号、班组、工单或个人权限，并带 definition version/ETag。

- [ ] **Step 2：更新缓存配置**

API 默认 `NetworkOnly`；只有明确列出的匿名静态定义快照允许缓存。页面壳可 precache，但退出后不得继续显示前一位工人的 sessionMetadata 或业务页面快照。

- [ ] **Step 3：实现公共设备退出清理**

退出顺序：停止同步 → 调用服务端 revoke → 清除 sessionMetadata → 删除当前 owner 草稿 → 对未提交 outbox 显示明确选择 → 清除内存状态 → 跳转登录。禁止默认删除尚未提交的 outbox。

- [ ] **Step 4：验证更新提示**

有未提交 outbox 时，新版本提示只能“稍后更新”；outbox 清空后才允许 reload。更新不应造成正在填写的数据丢失。

- [ ] **Step 5：运行测试和生产构建并提交**

Run: `cd frontend && npm test -w @form-detection/web -- pwa-cache-policy.test.ts session-cleanup.test.ts && npm run build -w @form-detection/web`

Expected: PASS；生产构建生成 manifest 和 Service Worker，私有 API 不进入 runtime cache。

```text
git add frontend/apps/web/vite.config.ts frontend/apps/web/src/pwa frontend/apps/web/src/mobile/MobileProfilePage.tsx frontend/apps/web/src/mobile/storage/db.ts frontend/apps/web/src/mobile/storage/session-cleanup.ts
git commit -m "fix(pwa): protect private data on shared devices"
```

### Task 8：移除原型状态并完成闭环验收

执行状态（2026-07-21）：Task 1—7 的实现与自动验证已完成；按用户要求仍保留在工作区，未擅自创建计划中的分步提交。Task 8 的自动验收与协作文档已完成，真机验收和提交仍待后续执行。

**Files:**
- Modify: `app/api/main_ds.py`
- Modify: `app/api/routers/mobile_ds.py`
- Delete: `app/modules/mobile/models_ds.py`
- Delete when unused: `frontend/apps/web/src/mobile/api.ts`
- Delete when unused: `frontend/apps/web/src/mobile/auth.ts`
- Update: `docs/PROJECT_TECHNICAL_OVERVIEW.md`
- Update: `docs/CURRENT_STATUS.md`
- Update: `docs/NEXT_TASK.md`
- Update: `docs/DECISIONS.md`
- Create: `docs/acceptance/PWA_MOBILE_ACCEPTANCE.md`
- Test: `tests/api/test_mobile_no_pilot_state_ds.py`
- Test: `frontend/apps/web/src/mobile/mobile-end-to-end.test.tsx`

- [x] **Step 1：建立禁止原型状态测试**

```python
def test_production_mobile_code_contains_no_demo_identity_or_process_store():
    forbidden = ("_PILOT_USERS", "_SESSIONS", "张三", "李四", "1234", "_form_schemas")
    sources = load_mobile_production_sources()
    for marker in forbidden:
        assert marker not in sources
```

该测试只扫描明确列出的移动生产源文件，不扫描整个仓库或历史文档。

- [x] **Step 2：删除旧接线**

确认没有 import 后删除 `app/modules/mobile/` 旧模型和前端旧 API/Auth 文件。`mobile_ds.py` 最终只聚合正式子路由；禁止留下双实现开关。

- [x] **Step 3：完成最小端到端闭环**

自动化覆盖：

1. 有效员工登录；
2. 加载已发布 Definition；
3. SELF 填写并提交；
4. TEAM_LEADER_BATCH 代填且服务端校验成员；
5. 断网保存、刷新恢复、联网补交；
6. 重复提交只产生一张 Form；
7. Form 出现在现有 NEEDS_REVIEW 工作台；
8. 审核确认生成 RecordVersion；
9. 现有导出可包含该记录。

- [x] **Step 4：进行一次完整自动检查**

只有在前 7 个任务完成后运行一次：

```text
uv run pytest -q -p no:cacheprovider
uv run ruff check app config tests --no-cache
uv run mypy app config
cd frontend
npm test
npm run typecheck -w @form-detection/web
npm run build -w @form-detection/web
```

Expected: 全部退出码为 0；记录数量摘要，不粘贴完整日志。

- [ ] **Step 5：人工移动端验收**

仅验证自动化无法代替的项目：Android/iOS 安装、横竖屏、弱网、断网恢复、公共设备换人登录、更新提示和现场术语。没有真实设备证据时，在验收文档中明确标记“待人工验证”，不得写“全部完成”。

- [x] **Step 6：更新协作文档**

- `CURRENT_STATUS.md` 写明实际完成项和测试摘要；
- `NEXT_TASK.md` 只保留尚未完成的人工/业务事项；
- `DECISIONS.md` 新增移动端单数据通道、HttpOnly 会话、客户端 outbox 和单事务提交决定；
- `PROJECT_TECHNICAL_OVERVIEW.md` 将相关模块从“部分实现”更新为真实状态。

- [ ] **Step 7：提交验收结果**

```text
git add app/api app/modules/mobile frontend/apps/web/src/mobile docs tests
git commit -m "docs(pwa): record production mobile acceptance"
```

## 4. 每个任务的验收停止条件

出现以下任一情况必须停止当前任务，不得扩大范围自行绕过：

- 需要修改已发布模板、历史 RecordVersion 或旧迁移内容；
- 主系统没有竹丝笼、班组关系或岗位授权的可靠数据源；
- 为了让页面“看起来能用”准备重新加入演示用户或固定工单；
- 提交事务无法保证 Form 与 Receipt 同成同败；
- Service Worker 需要缓存含个人或生产信息的 API 才能工作；
- 工作树中未提交文件归属不清，可能覆盖他人修改；
- 当前分支不再是 `codex/low-token-ui-v2`。

## 5. 合并到正式主线的硬门槛

- [x] 生产代码不含演示员工、演示 PIN、固定笼号、固定工单或 module-level 业务存储。
- [x] 移动身份、会话和锁定状态可跨服务重启保持。
- [x] Form、Field、Audit、Receipt 在同一事务中成功或回滚。
- [x] SELF 与 TEAM_LEADER_BATCH 的 actor/subject 权限由服务端验证。
- [x] 页面只使用共享类型化 API 客户端。
- [x] Token 不进入 localStorage、IndexedDB、URL 或日志。
- [x] 草稿和 outbox 在刷新、断网、重启后可恢复。
- [x] 401、403、409、422、5xx 和网络异常具有不同恢复行为。
- [x] Service Worker 不缓存身份、提交、草稿、生产上下文、证据或导出内容。
- [x] 电子提交可在现有审核工作台确认并进入现有导出。
- [x] 自动化完整检查通过；真机未验证项被明确记录。
- [ ] 当前工作树未提交内容均已确认归属并按任务拆分提交。

## 6. 预计提交顺序

```text
1. fix(mobile): make electronic submission atomic
2. feat(mobile): persist credentials and sessions
3. feat(mobile): route PWA through production services
4. feat(mobile): use typed cookie session client
5. feat(mobile): connect pages to durable submission flow
6. refactor(mobile): split form engine responsibilities
7. fix(pwa): protect private data on shared devices
8. docs(pwa): record production mobile acceptance
```

不得将 8 个任务压成一个大提交。简单功能使用局部测试；完整回归只在 Task 8 执行一次。
