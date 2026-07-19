# Job Profile HTTP API Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Reuse the application service; routes must not call SQLAlchemy directly.

**Goal:** 向本地前端提供岗位配置版本的创建、列表、详情、修改、发布、复制和停用接口。

**Files:**
- Modify: `app/services/container.py`
- Modify: `app/api/routers/templates_ds.py`
- Modify: `tests/api/test_templates_api_ds.py`

### Task 1: API 失败测试

- [ ] 覆盖创建草稿、按岗位键列表、详情、修改、发布、复制、停用的完整 JSON 契约。
- [ ] 覆盖未知配置 404、模板版本不匹配 409、无模板编辑权限 403。
- [ ] 断言响应包含核心版面、模板版本和岗位配置版本，不返回数据库内部字段。
- [ ] Run: `python -m pytest tests/api/test_templates_api_ds.py -q`，确认新路由不存在而失败。

### Task 2: 接入服务与路由

- [ ] `Services` 新增 `job_profiles`，由同一个模板仓储实现两个窄端口。
- [ ] 路由只调用 `services.job_profiles`；配置 ID 使用服务端生成的 `PROFILE-...`。
- [ ] 创建/修改使用 422，绑定/生命周期冲突使用 409，未知版本使用 404。
- [ ] 读取复用模板读取权限，写入复用模板版本创建权限；保持本地模式现有授权策略不变。
- [ ] Run: `python -m pytest tests/api/test_templates_api_ds.py -q`。

### Task 3: 局部质量检查

- [ ] Run: `ruff check app/services/container.py app/api/routers/templates_ds.py tests/api/test_templates_api_ds.py`。
- [ ] Run: `mypy app/services/container.py app/api/routers/templates_ds.py`。
- [ ] 不改前端，不运行完整测试。

