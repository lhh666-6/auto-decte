# Controlled Table Grid Primitive Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. This task changes only the reusable table primitive, not all six business layouts.

**Goal:** 让模板的“明细表”成为真正可打印的固定行列网格，而不是一个空外框。

**Files:**
- Modify: `app/domain/templates_ds.py`
- Modify: `app/adapters/templates/print_renderer_ds.py`
- Modify: `app/adapters/database/template_repository_ds.py`
- Modify: `tests/unit/test_templates_domain_ds.py`
- Modify: `tests/adapters/test_template_print_renderer_ds.py`
- Modify: `tests/adapters/test_template_repository_ds.py`

### Task 1: 失败测试

- [ ] `TABLE_GRID` 支持正整数 rows/columns 和可选 column_weights。
- [ ] 非 TABLE_GRID 不允许携带行列配置；列宽数量/正数校验失败时给清晰错误。
- [ ] 仓储 round-trip 保持行列与列宽。
- [ ] renderer 在网格区域产生内部横线、竖线，不只画外框。

### Task 2: 最小实现

- [ ] `StaticElement` 新增 rows、columns、column_weights，默认 1×1，保持旧模板兼容。
- [ ] JSON 序列化/反序列化兼容旧记录缺少新键。
- [ ] renderer 使用毫米/像素边界稳定绘制；列宽为空时等宽，有权重时按比例。
- [ ] 不在此任务增加复杂自由表格编辑器。

### Task 3: 局部验证

- [ ] 运行领域、renderer、模板仓储三个测试文件。
- [ ] 运行 Ruff 和相关 mypy，不运行 API、前端或完整套件。

