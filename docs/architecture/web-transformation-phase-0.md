# Web 转型阶段 0：边界冻结与依赖审计

日期：2026-07-23  
状态：已建立边界，等待阶段验收  
设计来源：`Web三角色端与后台服务转型开发设计.md`

## 1. Git 基线

- 基线提交：`c05349fd6b3423f51e2774f68a3027612fcf806d`
- 基线提交说明：`fix(dev): allow stable HTTPS test tunnel`
- 来源分支：`modular-architecture`
- 实施分支：`codex/web-transformation`
- 受保护目录：`frontend/apps/web/src/mobile/**`

阶段 0 没有修改移动端源码、数据库模型或 Alembic 历史迁移。

## 2. 移动端稳定契约

聚合入口是 `app/api/routers/mobile_ds.py`，统一前缀为
`/api/v1/mobile`。当前共有 55 个移动端端点：

| 子路由 | 路由文件 | 端点数 |
|---|---|---:|
| 认证 | `mobile_auth_ds.py` | 3 |
| 竹丝生产 | `mobile_bamboo_ds.py` | 43 |
| 生产上下文 | `mobile_context_ds.py` | 5 |
| 表单定义 | `mobile_definitions_ds.py` | 2 |
| 电子提交 | `mobile_submissions_ds.py` | 2 |

端点的完整方法与路径集合由
`tests/architecture/test_web_transformation_phase_0_ds.py` 中的
`EXPECTED_MOBILE_ROUTES` 冻结。关键入口包括：

- `POST /api/v1/mobile/auth/login`
- `GET /api/v1/mobile/auth/session`
- `POST /api/v1/mobile/auth/logout`
- `GET /api/v1/mobile/available-forms`
- `GET /api/v1/mobile/form-schemas/{form_type}`
- `GET /api/v1/mobile/context`
- `GET /api/v1/mobile/options/{catalog}`
- `GET /api/v1/mobile/production-contexts/current`
- `POST|GET /api/v1/mobile/submissions`
- `GET /api/v1/mobile/bamboo/inspection-queue`
- `POST /api/v1/mobile/bamboo/records`
- `POST /api/v1/mobile/bamboo/records/{record_id}/stages/{stage_key}/submit`
- `POST /api/v1/mobile/bamboo/records/{record_id}/inspection-submit`
- `GET /api/v1/mobile/bamboo/finance/monthly-summary`

### Schema 文件

- `app/api/schemas/mobile_ds.py`
- `app/api/schemas/bamboo_process_ds.py`

通用移动 Schema 共 19 个业务模型；竹丝流程 Schema 共 24 个业务模型。
关键请求和响应字段由阶段 0 契约测试精确冻结，包括：

- `LoginRequest`
- `LoginResponse`
- `SessionResponse`
- `CreateSubmissionRequest`
- `SubmissionResponse`
- `FormSchemaResponse`
- `CreateBambooRecordRequest`
- `SubmitBambooStageRequest`

后续共享 Schema 只能做向后兼容扩展：新字段默认可选，不改变旧字段语义，
枚举只追加兼容值。Web 三角色端应优先使用独立的
`/api/v1/finance`、`/api/v1/admin` 和 `/api/v1/plant` 边界。

## 3. 现有模块与旧识别链路

基线中有 15 个现有业务模块：

`audit`、`bamboo_process`、`electronic_forms`、`evidence`、
`fact_records`、`forms`、`identity_access`、`master_data`、
`recognition`、`reporting`、`review`、`rules`、`search`、`tasks`、
`templates`。

### 保留或迁移

| 现有能力 | 后续归属 |
|---|---|
| 员工、工厂、角色、会话 | `identity_access` |
| 电子表单定义和版本 | `electronic_forms` |
| 审计事件 | `audit` |
| 提交事实和幂等回执 | `submission_ledger` |
| 导出批次和下载 | `reporting` |
| 通用任务执行 | 通用作业执行器 |
| Excel 写出 | `report_templates` + `reporting` |

### 阶段 7 才能退役

- `app/modules/recognition`
- `app/adapters/recognition`
- 图片导入、分类、复核工作台及相关 API
- 图片证据专用存储
- 纸张识别模板和识别后台任务

相关依赖包括 NumPy、OpenCV、识别适配器、图片存储、导入与复核服务。
删除前必须再次检查 Python import、FastAPI 路由、SQLAlchemy 表引用、
前端 API Client 和移动端契约测试。本阶段不删除任何旧能力。

## 4. 可复用通用能力

- HttpOnly 会话、CSRF、请求编号和 Problem Details
- 工厂和角色权限边界
- SQLAlchemy、SQLite、Alembic 与仓储装配
- 不可变审计
- 表单版本、提交事实、幂等回执和更正关系
- 任务执行、文件存储、导出批次和下载
- 通用表格、筛选、状态和权限守卫

这些能力应迁移到新边界后复用，不能按旧目录名称整体删除。

## 5. 目标模块状态

已存在并继续使用：

- `identity_access`
- `electronic_forms`
- `reporting`
- `audit`

阶段 0 新建空包骨架：

- `admin_console`
- `business_knowledge`
- `business_discovery`
- `workflow_engine`
- `submission_ledger`
- `finance_ledger`
- `payroll_rules`
- `report_templates`
- `data_lineage`
- `notifications`
- `secret_config`

空包只声明目标边界，不导入彼此，也不包含业务逻辑。

## 6. 自动检查

- `scripts/check_mobile_boundary.py` 比较明确的 `--base` 和 `--head`。
- Git diff 失败时脚本返回 2，禁止把检查异常误判为通过。
- 发现移动目录变化时脚本返回 1。
- `.github/workflows/web-transformation-boundary.yml` 直接调用该脚本。
- CI 同时运行现有架构测试和阶段 0 移动契约测试。

本地验证示例：

```text
python scripts/check_mobile_boundary.py --base c05349f --head HEAD
python -m pytest -q tests/architecture/test_contracts_ds.py tests/architecture/test_web_transformation_phase_0_ds.py
```

## 7. 阶段 0 退出条件

- [x] Git 基线已记录
- [x] 移动端 API 和关键 Schema 已冻结
- [x] 移动端契约测试已建立
- [x] 移动目录变更检查已建立
- [x] CI 调用边界脚本和契约测试
- [x] 旧识别链路与通用能力已盘点
- [x] 共享 Schema 影响已明确
- [x] 目标模块骨架已建立

进入阶段 1 后，移动端仍保持现有主动填报模式；三角色 Web 工作区通过新路由
和兼容 API 接入。
