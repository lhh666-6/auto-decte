# 模块化工业程序增量架构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不重写现有表单闭环的前提下，建立 FastAPI 模块化单体、任务、权限、审核锁、事务、迁移、运维和 React/Tauri 契约边界。

**Architecture:** 保留 `app/domain`、`app/application`、`app/adapters` 中已验证逻辑，新增 `app/api` 与 `app/modules` Facade。新命令通过 SQLAlchemy UnitOfWork 协调业务、版本和审计；现有 Repository 在兼容期由 UoW Session 驱动。SQLite 是当前事实源，任务、身份、存储、错误追踪和向量能力通过 Port 可替换。

**Tech Stack:** Python 3.11、FastAPI、Starlette SSE、Pydantic v2、SQLAlchemy 2、Alembic、SQLite、pytest、Ruff、mypy；前端仅建立 TypeScript/OpenAPI 与 Shell Port 骨架。

---

## 前置状态与风险

- 当前 `main` 有用户未提交的 `docs/acceptance-report.md` 修改、`.runtime/`、`.superpowers/` 和 Word 原稿；不得暂存、覆盖或提交它们。
- 用户将旧计划 `docs/superpowers/plans/2026-07-12-industrial-form-demo.md` 标记为删除，并新增 `docs/superpowers/plans/模块化工业程序增量架构设计_完善版.md`；不得恢复旧文件或改写新文件。
- 当前仓库没有 FastAPI，`SqlAlchemyFormRepository` 每个方法内部提交事务。任务 3 先建立 UoW 兼容层，之后才迁移写命令。
- 用户明确禁止推送远程仓库和部署服务器；每个提交只保留本地。

## 目标文件结构

```text
app/
  api/
    main.py
    dependencies.py
    errors/problem.py
    middleware/request_id.py
    routers/{health,identity,forms,review,tasks,exports}.py
    schemas/{common,forms,review,tasks}.py
  modules/
    forms/facade.py
    evidence/facade.py
    recognition/facade.py
    review/{facade,lease_service}.py
    rules/facade.py
    search/facade.py
    reporting/facade.py
    audit/facade.py
    tasks/{models,ports,service}.py
    identity_access/{models,ports,policy,local}.py
    master_data/facade.py
    templates/facade.py
  infrastructure/
    database/{uow,sqlite,alembic}.py
    tasks/{sqlite_store,in_process}.py
    observability/{logging,error_tracker}.py
    backup/{service,integrity}.py
  tools/verify_integrity.py
alembic/
frontend/
  package.json
  packages/{api-client,shell-ports}/src/
  apps/{web,desktop}/README.md
docs/{architecture,operations,migration}/
tests/{api,architecture,integration,unit}/
```

### Task 1: 建立模块入口、设置项和 SQLite 连接约束

**Files:**
- Create: `app/modules/__init__.py`, `app/modules/*/__init__.py`
- Create: `app/infrastructure/database/sqlite.py`
- Modify: `config/settings.py`
- Modify: `app/services/container.py`
- Test: `tests/unit/test_sqlite_configuration.py`

- [ ] **Step 1: 写失败测试，验证 SQLite 连接开启 WAL、foreign keys 和 busy timeout**

```python
def test_sqlite_engine_enables_wal_foreign_keys_and_busy_timeout(tmp_path: Path) -> None:
    engine = create_sqlite_engine(tmp_path / "demo.db")
    with engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA journal_mode").scalar_one().lower() == "wal"
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1
        assert connection.exec_driver_sql("PRAGMA busy_timeout").scalar_one() >= 5000
```

- [ ] **Step 2: 运行红灯测试**

Run: `uv run python -m pytest tests/unit/test_sqlite_configuration.py -v`

Expected: FAIL because `create_sqlite_engine` does not exist.

- [ ] **Step 3: 实现最小 SQLite 工厂和 Settings**

```python
def create_sqlite_engine(path: Path) -> Engine:
    engine = create_engine(f"sqlite:///{path}", connect_args={"check_same_thread": False})
    event.listen(engine, "connect", _configure_connection)
    return engine

def _configure_connection(connection: sqlite3.Connection, _: object) -> None:
    connection.execute("PRAGMA foreign_keys=ON")
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
```

新增 `task_max_workers`、`task_queue_capacity`、`review_lease_seconds`、`api_host`、`api_port` 和 `local_default_user_id` 设置；容器只能通过该工厂创建 Engine。

- [ ] **Step 4: 验证、格式化并提交**

Run: `uv run python -m pytest tests/unit/test_sqlite_configuration.py -v && uv run python -m ruff check app config tests`

Commit: `refactor: add modular infrastructure entrypoints`

### Task 2: 定义身份、角色、权限和本地 Identity Provider

**Files:**
- Create: `app/modules/identity_access/{models,ports,policy,local}.py`
- Create: `tests/unit/test_identity_access.py`
- Modify: `config/settings.py`

- [ ] **Step 1: 写失败权限矩阵测试**

```python
def test_operator_cannot_confirm_and_reviewer_can_confirm() -> None:
    policy = PermissionPolicy()
    operator = Actor("operator-1", frozenset({Role.OPERATOR}))
    reviewer = Actor("reviewer-1", frozenset({Role.REVIEWER}))
    assert policy.allows(operator, Permission.REVIEW_CONFIRM) is False
    assert policy.allows(reviewer, Permission.REVIEW_CONFIRM) is True
```

- [ ] **Step 2: 运行红灯测试**

Run: `uv run python -m pytest tests/unit/test_identity_access.py -v`

Expected: FAIL because `Actor` and `PermissionPolicy` do not exist.

- [ ] **Step 3: 实现 Role、Permission、Actor、IdentityProvider 和 Policy**

定义 `ADMIN`、`OPERATOR`、`REVIEWER`、`FINANCE`、`AUDITOR`；为 `form.read`、`form.import`、`review.acquire`、`review.confirm`、`review.correct`、`review.void`、`export.create`、`audit.read`、`evidence.audio.read`、`task.cancel`、`task.retry` 建立固定权限矩阵。`LocalIdentityProvider` 从 Settings 读取默认用户与角色，不默认管理员。

- [ ] **Step 4: 覆盖审计员只读、财务导出、管理员强制释放和未认证情形**

Run: `uv run python -m pytest tests/unit/test_identity_access.py -v`

Expected: PASS.

- [ ] **Step 5: 提交**

Commit: `feat: add local identity and permission policy`

### Task 3: 引入 UnitOfWork 与兼容 Repository Facade

**Files:**
- Create: `app/infrastructure/database/uow.py`
- Create: `app/modules/forms/facade.py`, `app/modules/audit/facade.py`
- Modify: `app/adapters/database/repositories.py`
- Modify: `app/application/review_forms.py`
- Test: `tests/integration/test_unit_of_work.py`

- [ ] **Step 1: 写失败测试，验证版本与审计原子提交**

```python
def test_confirmation_rolls_back_version_when_audit_insert_fails(repository: SqlAlchemyFormRepository) -> None:
    facade = ReviewFacade(uow_factory=..., forms=..., audits=FailingAuditRepository())
    with pytest.raises(RuntimeError):
        facade.confirm(command)
    assert repository.list_record_versions("FORM-1") == []
```

- [ ] **Step 2: 运行红灯测试**

Run: `uv run python -m pytest tests/integration/test_unit_of_work.py -v`

Expected: FAIL because `SqlAlchemyUnitOfWork` and `ReviewFacade` do not exist.

- [ ] **Step 3: 实现 UoW 与 Session-bound Repository**

```python
class UnitOfWork(Protocol):
    def __enter__(self) -> Self: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...

class SqlAlchemyUnitOfWork:
    def __enter__(self) -> Self:
        self.session = self._session_factory()
        self.transaction = self.session.begin()
        return self
```

为现有 Repository 增加可选 `Session` 构造参数；有 Session 时绝不创建内部事务。保留旧无 Session 路径以保证现有服务和测试兼容。`ReviewFacade.confirm` 在一个 UoW 中验证、追加 RecordVersion、更新状态并追加 AuditEvent。

- [ ] **Step 4: 验证成功、业务失败和审计失败回滚路径**

Run: `uv run python -m pytest tests/integration/test_unit_of_work.py tests/unit/test_review_service.py -v`

- [ ] **Step 5: 提交**

Commit: `refactor: add unit of work review facade`

### Task 4: ReviewLease、乐观并发和审核 Facade

**Files:**
- Create: `app/modules/review/{models,lease_service,facade}.py`
- Modify: `app/adapters/database/models.py`, `app/adapters/database/repositories.py`
- Test: `tests/integration/test_review_lease.py`

- [ ] **Step 1: 写失败 Lease 测试**

```python
def test_second_reviewer_cannot_acquire_live_lease(clock: FrozenClock) -> None:
    first = leases.acquire("FORM-1", "reviewer-a")
    with pytest.raises(LeaseHeldError):
        leases.acquire("FORM-1", "reviewer-b")
    assert first.owner_id == "reviewer-a"
```

- [ ] **Step 2: 写失败确认冲突测试**

```python
def test_confirm_rejects_stale_version_with_conflict_context() -> None:
    result = facade.confirm(ConfirmCommand(..., expected_version=1, lease_token="..."))
    assert result.current_version == 2
```

Expected: test raises `ReviewVersionConflict` before result is returned.

- [ ] **Step 3: 实现 `ReviewLeaseRow`、Lease Repository 和服务**

字段为 form_id、owner_id、lease_token、acquired_at、expires_at、heartbeat_at、forced_release_by、forced_release_reason。使用唯一 form_id；获取时清理过期锁；heartbeat 仅允许 owner/token；管理员强制释放必须给 reason；每个操作写 AuditEvent。

- [ ] **Step 4: 将 `ReviewFacade.confirm` 改为验证权限、Lease、expected_version、规则与状态**

冲突抛出包含 submitted_version 和 current_version 的 `ReviewVersionConflict`。确认成功时释放 Lease 或按命令显式保留。

- [ ] **Step 5: 运行锁、过期、续租、非持有者、强制释放和 409 对应单元测试**

Run: `uv run python -m pytest tests/integration/test_review_lease.py -v`

- [ ] **Step 6: 提交**

Commit: `feat: add review leases and optimistic concurrency`

### Task 5: SQLite 持久化任务、事件、幂等和 InProcess Runner

**Files:**
- Create: `app/modules/tasks/{models,ports,service}.py`
- Create: `app/infrastructure/tasks/{sqlite_store,in_process}.py`
- Modify: `app/adapters/database/models.py`
- Test: `tests/integration/test_tasks.py`, `tests/unit/test_task_state_machine.py`

- [ ] **Step 1: 写失败状态机测试**

```python
def test_pending_task_moves_to_running_then_succeeded() -> None:
    task = Task.new("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1")
    assert task.transition(TaskStatus.RUNNING).status is TaskStatus.RUNNING
    assert task.transition(TaskStatus.SUCCEEDED).progress == 100
```

- [ ] **Step 2: 写失败幂等测试**

```python
def test_same_idempotency_key_and_payload_returns_existing_task() -> None:
    assert service.submit(command) == service.submit(command)
```

- [ ] **Step 3: 实现 Task、TaskEvent、TaskStore 和状态迁移**

状态固定为 `PENDING`、`RUNNING`、`SUCCEEDED`、`FAILED`、`CANCEL_REQUESTED`、`CANCELLED`、`INTERRUPTED`。每个事件写递增 sequence。相同 actor、operation、resource、key、payload_hash 返回已有任务；相同 key 但不同 payload_hash 抛 `IdempotencyConflict`。

- [ ] **Step 4: 实现受限 InProcessTaskRunner**

使用 `ThreadPoolExecutor(max_workers=settings.task_max_workers)` 和 `BoundedSemaphore(settings.task_queue_capacity)`。任务函数收到 `TaskContext.report(progress, step)` 和 `TaskContext.cancel_requested()`；不持有 UoW 进入耗时识别或导出。

- [ ] **Step 5: 实现启动恢复**

启动时将 RUNNING 标记 INTERRUPTED 并写 event；PENDING 可由显式 `recover_pending()` 重入队；导出默认不可自动重试。

- [ ] **Step 6: 运行任务创建、进度、取消、失败、重试、幂等和重启恢复测试**

Run: `uv run python -m pytest tests/unit/test_task_state_machine.py tests/integration/test_tasks.py -v`

- [ ] **Step 7: 提交**

Commit: `feat: add persistent in-process task orchestration`

### Task 6: FastAPI 基础、Problem Details、Request ID 和健康检查

**Files:**
- Create: `app/api/main.py`, `app/api/dependencies.py`
- Create: `app/api/errors/problem.py`, `app/api/middleware/request_id.py`
- Create: `app/api/routers/{health,identity}.py`
- Create: `app/api/schemas/common.py`
- Modify: `pyproject.toml`, `README.md`
- Test: `tests/api/test_health_and_errors.py`

- [ ] **Step 1: 写失败 API 测试**

```python
def test_live_health_returns_request_id(client: TestClient) -> None:
    response = client.get("/health/live", headers={"X-Request-ID": "REQ-test"})
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "REQ-test"
    assert response.json() == {"status": "live"}
```

```python
def test_unhandled_error_uses_problem_details_without_traceback(client: TestClient) -> None:
    response = client.get("/api/v1/testing/fail")
    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert "traceback" not in response.text.lower()
```

- [ ] **Step 2: 运行红灯测试**

Run: `uv run python -m pytest tests/api/test_health_and_errors.py -v`

- [ ] **Step 3: 添加 FastAPI、SSE 依赖和应用工厂**

在 `pyproject.toml` 添加 `fastapi`、`uvicorn`、`httpx`（dev）。`create_app(container: Services) -> FastAPI` 注册 `/health/live`、`/health/ready`、`/api/v1/me`。Request ID middleware 读取或生成 UUID，写入 `request.state` 和响应头。异常映射到 Pydantic `ProblemDetails`。

- [ ] **Step 4: 实现 ready capability 返回**

`ready` 验证数据库查询、证据目录创建权限、任务 runner；返回 `capabilities.ai`、`capabilities.vector`、`capabilities.audio_transcription`，可选能力降级不使核心 ready 失败。

- [ ] **Step 5: 验证 OpenAPI 与错误结构**

Run: `uv run python -m pytest tests/api/test_health_and_errors.py -v && uv run python -c "from app.api.main import create_app; assert create_app(...).openapi()['openapi'].startswith('3.')"`

- [ ] **Step 6: 提交**

Commit: `feat: add fastapi foundation and health endpoints`

### Task 7: 表单、证据、审核锁和任务 API 加 SSE

**Files:**
- Create: `app/api/routers/{forms,review,tasks,exports}.py`
- Create: `app/api/schemas/{forms,review,tasks}.py`
- Modify: `app/api/main.py`, `app/api/dependencies.py`
- Test: `tests/api/test_forms_review_tasks.py`, `tests/api/test_task_sse.py`

- [ ] **Step 1: 写失败鉴权和 Lease API 测试**

```python
def test_operator_gets_403_when_confirming(client: TestClient) -> None:
    response = client.post("/api/v1/forms/FORM-1/confirm", headers=operator_headers, json=payload)
    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
```

```python
def test_reviewer_acquires_lease_and_stale_confirm_returns_409(client: TestClient) -> None:
    lease = client.post("/api/v1/forms/FORM-1/review-lease", headers=reviewer_headers).json()
    response = client.post("/api/v1/forms/FORM-1/confirm", headers=reviewer_headers, json={**payload, "lease_token": lease["lease_token"], "expected_version": 0})
    assert response.status_code == 409
    assert response.json()["code"] == "REVIEW_VERSION_CONFLICT"
```

- [ ] **Step 2: 写失败 SSE 续传测试**

```python
def test_task_events_resume_after_last_event_id(client: TestClient) -> None:
    response = client.get("/api/v1/tasks/TASK-1/events", headers={"Last-Event-ID": "2"})
    assert "id: 3" in response.text
```

- [ ] **Step 3: 实现 DTO 与路由**

表单详情响应使用 `FormDetailResponse`，不返回 ORM 或绝对路径；证据 API 返回受控 file_id URL。确认请求包含 expected_version、lease_token、values、reason、evidence_ids。任务创建返回 202、task_id、status_url、events_url。SSE 仅发送调用者有 `task.read` 权限的事件。

- [ ] **Step 4: 添加 Idempotency-Key 和 If-Match 解析**

写路由读取 Idempotency-Key；确认、修改和导出将 `If-Match` 或 expected_version 统一传入 Facade。键复用但 body 改变返回 Problem Details 409。

- [ ] **Step 5: 运行 API 回归测试**

Run: `uv run python -m pytest tests/api -v`

- [ ] **Step 6: 提交**

Commit: `feat: expose versioned review and task api`

### Task 8: Alembic、备份、恢复前校验和一致性检查

**Files:**
- Create: `alembic.ini`, `alembic/env.py`, `alembic/versions/<revision>_architecture_baseline.py`
- Create: `app/infrastructure/backup/{service,integrity}.py`
- Create: `app/tools/verify_integrity.py`
- Create: `tests/integration/test_migrations_backup_integrity.py`
- Create: `docs/operations/{migration,backup-recovery}.md`

- [ ] **Step 1: 写失败空库迁移和备份测试**

```python
def test_alembic_upgrade_creates_task_and_review_lease_tables(tmp_path: Path) -> None:
    upgrade_database(tmp_path / "demo.db")
    assert {"tasks", "task_events", "review_leases"} <= table_names(tmp_path / "demo.db")
```

```python
def test_backup_manifest_detects_missing_evidence(tmp_path: Path) -> None:
    manifest = BackupService(...).create("operator")
    Path(manifest.evidence_files[0].path).unlink()
    assert IntegrityChecker(...).run().exit_code != 0
```

- [ ] **Step 2: 运行红灯测试**

Run: `uv run python -m pytest tests/integration/test_migrations_backup_integrity.py -v`

- [ ] **Step 3: 建立 Alembic 基线与升级接口**

初始 revision 从所有现有表以及 Task、TaskEvent、ReviewLease、IdempotencyRecord 创建。`app/services/container.py` 在生产模式只验证 revision，不调用 create_all；开发空库可显式 `uv run alembic upgrade head`。

- [ ] **Step 4: 实现 BackupService 与 IntegrityChecker**

备份使用 `sqlite3.Connection.backup()` 写入临时目录，计算数据库、证据、导出、模板的 SHA-256，再原子写入 `manifest.json`。检查器只报告问题，输出 JSON 和摘要；缺证据、哈希错误、孤立裁切、无效版本指针、无效导出、过期 Lease、RUNNING 任务均产生非零退出码。

- [ ] **Step 5: 写恢复演练测试**

先恢复到临时目录，执行完整性检查，成功后由 `RestorePlan` 返回可切换路径；测试失败时原 `data_root` 字节不变。

- [ ] **Step 6: 运行迁移、备份和检查测试**

Run: `uv run python -m pytest tests/integration/test_migrations_backup_integrity.py -v && uv run python -m app.tools.verify_integrity --help`

- [ ] **Step 7: 提交**

Commit: `feat: add migrations backup and integrity checks`

### Task 9: 可观测性和模块 Facade 文档

**Files:**
- Create: `app/infrastructure/observability/{logging,error_tracker}.py`
- Create: `app/modules/{forms,evidence,recognition,rules,search,reporting,audit,master_data,templates}/facade.py`
- Create: `tests/unit/test_observability.py`
- Modify: `README.md`, `docs/architecture/modular-monolith.md`

- [ ] **Step 1: 写失败日志上下文测试**

```python
def test_log_context_includes_request_actor_module_and_task() -> None:
    payload = JsonLogFormatter().format_record(record_with(request_id="REQ-1", actor_id="reviewer-1"))
    assert json.loads(payload)["request_id"] == "REQ-1"
```

- [ ] **Step 2: 实现 JsonLogFormatter、LocalErrorTracker 和 Module Facade**

日志固定写 timestamp、level、request_id、actor_id、module、event、operation、form_id、task_id、duration_ms、result、error_code；敏感字段过滤。每个 Facade 只导出明确 Application 命令和查询，不直接公开 SQLAlchemy Repository。

- [ ] **Step 3: 验证 API request_id 进入日志且可选 AI 降级**

Run: `uv run python -m pytest tests/unit/test_observability.py tests/api/test_health_and_errors.py -v`

- [ ] **Step 4: 提交**

Commit: `feat: add observability and module facades`

### Task 10: React/Web/Tauri 契约骨架和 Streamlit 迁移标记

**Files:**
- Create: `frontend/package.json`, `frontend/tsconfig.json`
- Create: `frontend/packages/api-client/src/{generated.ts,problem.ts,index.ts}`
- Create: `frontend/packages/shell-ports/src/{ports,web,desktop,index}.ts`
- Create: `frontend/apps/{web,desktop}/README.md`
- Create: `frontend/features/{review-workbench,task-queues,master-data,templates,dashboard,exports-trace}/README.md`
- Modify: `app/ui/main.py`, `README.md`, `docs/architecture/react-migration.md`
- Test: `frontend/packages/shell-ports/src/ports.test.ts`

- [ ] **Step 1: 写失败 TypeScript Shell Port 测试**

```ts
import type { ShellPorts } from "./ports";

const webPorts: ShellPorts = {
  files: { pick: async () => [] },
  camera: { capture: async () => null },
  scanner: { read: async () => null },
  audio: { record: async () => null },
  notifications: { notify: () => undefined },
};
void webPorts;
```

- [ ] **Step 2: 运行红灯类型检查**

Run: `npm --prefix frontend run typecheck`

Expected: FAIL because frontend workspace and ports do not exist.

- [ ] **Step 3: 实现零 UI 依赖的前端契约**

定义 FilePort、CameraPort、ScannerPort、AudioPort、NotificationPort。`web.ts` 使用浏览器能力；`desktop.ts` 仅暴露注入接口，禁止引入 `@tauri-apps/*`。`problem.ts` 定义 Problem Details 解析，`generated.ts` 只保留 OpenAPI 生成代码的目标位置和禁止手写 DTO 的说明。

- [ ] **Step 4: 标记 Streamlit 为诊断界面并修复自动空白页**

将页面函数移动出 Streamlit 自动发现的 `pages/` 路径或改为显式导航入口；保留诊断启动命令，README 说明 React 将首先迁移审核工作台和任务队列。

- [ ] **Step 5: 验证 TypeScript 与既有 Python UI**

Run: `npm --prefix frontend run typecheck && uv run python -m pytest -q`

- [ ] **Step 6: 提交**

Commit: `feat: add react shell and api contract boundaries`

### Task 11: 端到端架构验收与文档更新

**Files:**
- Create: `tests/architecture/test_architecture_contracts.py`
- Create: `docs/operations/{runbook,local-start}.md`
- Modify: `docs/acceptance-report.md` only if user explicitly asks to include architecture results
- Modify: `PROGRESS.md` only after preserving the user’s current entries

- [ ] **Step 1: 写架构契约测试**

```python
def test_domain_does_not_import_frameworks() -> None:
    source = Path("app/domain").read_text(encoding="utf-8")
    assert "fastapi" not in source.lower()
    assert "sqlalchemy" not in source.lower()
```

```python
def test_openapi_exposes_v1_routes_and_task_events() -> None:
    schema = create_app(test_container).openapi()
    assert "/api/v1/tasks/{task_id}/events" in schema["paths"]
```

- [ ] **Step 2: 执行完整质量门**

Run: `uv run python -m pytest -q && uv run python -m ruff check . && uv run python -m mypy app config && npm --prefix frontend run typecheck`

Expected: all checks pass.

- [ ] **Step 3: 执行本地启动冒烟**

Run: `uv run uvicorn app.api.main:create_app --factory --host 127.0.0.1 --port 8000`

Expected: `GET /health/live` returns 200, `GET /health/ready` returns 200 with capability statuses, and `/openapi.json` returns OpenAPI 3.

- [ ] **Step 4: 更新运行、迁移、备份、恢复、协作和 React 迁移文档**

明确列出不完成项：真实样表准确率、真实 SSO、Worker、PostgreSQL/NAS/S3/Qdrant、完整 React/Tauri UI 和设备 SDK。

- [ ] **Step 5: 本地提交，不推送**

Commit: `test: verify modular architecture foundation`

## 计划自检

| 完善版要求 | 实施任务 |
|---|---|
| 模块化单体、Port、Adapter、UoW | 1、3、9 |
| 任务、事件、幂等、恢复、SSE | 5、7 |
| 身份、权限、Lease、乐观锁 | 2、4、7 |
| API、OpenAPI、Problem Details、request_id | 6、7、11 |
| 追加审计和导出快照 | 3、4、7、11 |
| SQLite、迁移、备份、恢复、完整性 | 1、8 |
| React/Tauri Shell、Streamlit 迁移 | 10 |
| 日志、健康、错误追踪 | 6、9 |
| 文档、回归、质量门 | 8、10、11 |

风险与回滚点：每个任务完成后本地提交；若新 Facade 影响现有用例，保留旧服务入口并回退到该任务前提交。迁移仅对临时数据库和备份副本演练；禁止运行生产迁移、推送远程仓库或部署服务器。
