# Recognition Job Profile Identity Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Preserve legacy forms and legacy IFD QR behavior.

**Goal:** 识别 IFD2 后把岗位配置键和版本与表单一起持久保存，使后续审核和导出不会丢失岗位身份。

**Files:**
- Modify: `app/domain/models.py`
- Modify: `app/adapters/database/models.py`
- Modify: `app/adapters/database/repositories.py`
- Modify: `app/application/recognize_forms.py`
- Add: `alembic/versions/010_form_job_profile_identity_ds.py`
- Modify: `app/infrastructure/database/migrations.py`
- Modify: targeted repository/recognition/migration tests

### Task 1: 失败测试

- [ ] IFD2 分类结果返回 profile key/version，并把它保存到 Form。
- [ ] IFD 旧二维码分类后两个 profile 字段为 null。
- [ ] IFD2 的岗位配置不存在、未发布或模板绑定不一致时进入人工分类，不猜测。
- [ ] 迁移从 009 到 010 后旧表单仍存在且 profile 字段为空。

### Task 2: 领域、仓储、迁移

- [ ] Form 新增可空 `job_profile_key` / `job_profile_version`。
- [ ] `forms` 增加两列；010 只做加列，downgrade 只移除新列。
- [ ] `set_template` 同时接受可空岗位身份；所有旧调用保持兼容。
- [ ] 模板仓储增加按岗位键/版本读取已存在的方法供识别窄端口使用。

### Task 3: IFD2 分类

- [ ] 优先解析 IFD2，再解析 IFD；同一图多份冲突仍进入人工分类。
- [ ] 同时验证模板已发布、岗位配置已发布、岗位配置绑定该模板版本。
- [ ] 审计 after 记录岗位配置身份；不改 OCR 和裁片逻辑。

### Task 4: 局部验证

- [ ] 运行 form repository、recognition attempts、migration integrity 三个测试文件。
- [ ] 运行 Ruff 与相关 mypy，不运行前端或完整套件。

