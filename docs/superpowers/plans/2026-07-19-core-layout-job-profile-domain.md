# Core Layout and Job Profile Domain Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Execute only this domain task; persistence, API, seeds, renderer, QR, and UI are separate follow-up tasks.

**Goal:** 建立 V2“6 个核心纸质版面 + 可版本化岗位配置”的领域边界，使岗位差异不再继续复制成新的独立模板。

**Architecture:** 保留现有 `TemplateVersion` 作为纸面版面版本；新增严格的核心版面分类和 `PayrollJobProfileVersion` 领域对象。岗位配置只保存岗位名称、核心版面版本引用、单位/固定选项/单价/扣减规则/导出映射等配置，不保存坐标。已发布岗位配置不可修改。此任务不迁移现有 10 个模板，也不改变当前运行数据。

**Tech Stack:** Python 3.12、dataclasses、pytest。

---

### Task 1: 先用测试固定领域契约

**Files:**
- Modify: `tests/unit/test_templates_domain_ds.py`

- [ ] 导入 `CoreLayoutKind`、`JobProfileStatus`、`PayrollJobProfileVersion`。
- [ ] 断言核心版面枚举只能表达：计时、设备/叉车、装架/干燥计件、炉类、热压、开片六类。
- [ ] 断言岗位配置草稿必须绑定明确的 `template_version_id` 和正整数 `template_version`。
- [ ] 断言配置键使用大写 ASCII；固定选项、单价规则、扣减规则和导出映射使用独立字典，构造时复制输入，避免外部对象静默改写。
- [ ] 断言发布前必须显式进入就绪状态，发布后所有修改方法拒绝执行。
- [ ] 断言可从已发布配置复制下一版本草稿，同时保留父版本 ID。
- [ ] Run: `python -m pytest tests/unit/test_templates_domain_ds.py -q`
- [ ] Expected: 新测试因领域类型不存在而失败。

### Task 2: 实现最小领域模型

**Files:**
- Modify: `app/domain/templates_ds.py`

- [ ] 新增 `CoreLayoutKind` 六值枚举，不加入第七种业务模板。
- [ ] 新增 `JobProfileStatus`：`DRAFT`、`READY_TO_PUBLISH`、`PUBLISHED`、`RETIRED`。
- [ ] 新增 `PayrollJobProfileVersion`，字段至少包括：配置版本 ID、配置键、版本号、显示名称、核心版面种类、绑定的模板版本 ID/版本号、状态、父版本 ID、单位、固定选项、单价规则、扣减规则、导出映射。
- [ ] 提供 `draft(...)`、配置更新、`mark_ready_to_publish()`、`publish()`、`retire()`、`clone_as_draft(...)`；发布和停用状态不可变。
- [ ] 对配置键、版本、显示名称、模板引用和字典键做清晰校验；不要引入数据库、FastAPI 或渲染依赖。
- [ ] Run: `python -m pytest tests/unit/test_templates_domain_ds.py -q`
- [ ] Expected: 该文件全部通过。

### Task 3: 局部质量检查

**Files:**
- Verify only: `app/domain/templates_ds.py`
- Verify only: `tests/unit/test_templates_domain_ds.py`

- [ ] Run: `ruff check app/domain/templates_ds.py tests/unit/test_templates_domain_ds.py`
- [ ] Run: `mypy app/domain/templates_ds.py`
- [ ] 不运行模板种子、API、前端或完整测试；本任务没有改变它们。
- [ ] 更新 `docs/CURRENT_STATUS.md` 和 `docs/NEXT_TASK.md`，下一任务应为岗位配置持久化，不得直接跳到六张版面或 AI。

