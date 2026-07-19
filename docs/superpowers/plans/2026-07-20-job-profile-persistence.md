# Job Profile Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Do not seed, migrate, or delete the user's existing profile/template records in this task.

**Goal:** 让岗位配置版本可安全保存、查询和升级数据库，同时保持现有模板与历史数据不变。

**Architecture:** 在现有模板仓储旁新增 `job_profile_versions` 表，记录完整不可变配置快照并通过 `template_version_id` 绑定纸面版面版本。使用新增 Alembic 009 做纯增量建表；自动创建的新数据库由 SQLAlchemy metadata 同步获得该表。

**Files:**
- Modify: `app/adapters/database/models.py`
- Modify: `app/adapters/database/template_repository_ds.py`
- Modify: `tests/adapters/test_template_repository_ds.py`
- Add: `alembic/versions/009_job_profile_versions_ds.py`
- Modify: `app/infrastructure/database/migrations.py`
- Modify: `tests/integration/test_migrations_backup_integrity_ds.py`

### Task 1: 仓储失败测试

- [ ] 添加岗位配置草稿 round-trip、按键和版本查询、顺序列表测试。
- [ ] 添加已发布配置只允许状态推进、不能替换配置内容的测试。
- [ ] Run: `python -m pytest tests/adapters/test_template_repository_ds.py -q`，确认因缺模型/方法而失败。

### Task 2: 表模型与仓储

- [ ] 新增 `JobProfileVersionRow`，唯一约束为 `(profile_key, version)`；模板版本使用外键。
- [ ] 在 `SqlAlchemyTemplateRepository` 增加 add/get/get-by-key-version/list/replace 岗位配置方法。
- [ ] JSON 配置从领域对象完整 round-trip；不修改现有模板方法。
- [ ] 已发布配置只允许变为停用；身份、模板绑定和配置内容不得变化。
- [ ] Run: `python -m pytest tests/adapters/test_template_repository_ds.py -q`。

### Task 3: 增量迁移

- [ ] 新增 Alembic `009`，只创建 `job_profile_versions`；downgrade 只删除该新表。
- [ ] 把 `HEAD_REVISION` 更新为 `009`。
- [ ] 迁移测试断言新表、唯一约束/索引存在，并验证从 `008` 升级后旧模板仍可读取。
- [ ] Run: `python -m pytest tests/integration/test_migrations_backup_integrity_ds.py -q`。

### Task 4: 局部质量检查

- [ ] Run: `ruff check` 仅覆盖上述 Python 文件。
- [ ] Run: `mypy app/domain/templates_ds.py app/adapters/database/template_repository_ds.py`。
- [ ] 不读取或迁移实际数据库内容，不运行前端和完整测试。

