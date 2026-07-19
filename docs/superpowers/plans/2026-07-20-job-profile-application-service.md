# Job Profile Application Service Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. This task stops before HTTP/API and UI.

**Goal:** 为岗位配置版本提供可测试的创建、读取、修改、发布、复制和停用用例，API 不直接操作数据库仓储。

**Files:**
- Add: `app/application/job_profiles_ds.py`
- Add: `tests/application/test_job_profiles_ds.py`

### Task 1: 失败测试

- [ ] 用内存仓储覆盖创建草稿、读取、按岗位键列表、更新配置。
- [ ] 发布前确认绑定的模板版本存在且版本号一致；不存在或不一致返回清晰错误。
- [ ] 覆盖发布、从已发布版本复制下一草稿、停用；发布后直接修改必须失败。
- [ ] Run: `python -m pytest tests/application/test_job_profiles_ds.py -q`，确认模块不存在而失败。

### Task 2: 最小应用服务

- [ ] 定义窄 `JobProfileRepository` 与 `TemplateVersionLookup` Protocol。
- [ ] 实现 `JobProfiles` 用例，不导入 FastAPI、SQLAlchemy 或前端类型。
- [ ] 使用调用方传入的新版本 ID，不在服务内依赖随机数，保证测试可重复。
- [ ] Run: `python -m pytest tests/application/test_job_profiles_ds.py -q`。

### Task 3: 局部质量检查

- [ ] Run: `ruff check app/application/job_profiles_ds.py tests/application/test_job_profiles_ds.py`。
- [ ] Run: `mypy app/application/job_profiles_ds.py`。
- [ ] 不运行迁移、API、前端或全套测试。

