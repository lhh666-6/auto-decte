# Template and Job Profile Dual-Version QR Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Preserve legacy `IFD` QR parsing.

**Goal:** 新打印实例的二维码同时绑定纸面模板版本和岗位配置版本，旧纸张仍可识别。

**Files:**
- Modify: `app/domain/templates_ds.py`
- Modify: `tests/unit/test_templates_domain_ds.py`
- Modify: `app/adapters/templates/print_renderer_ds.py`
- Modify: `tests/adapters/test_template_print_renderer_ds.py`

### Task 1: 双版本载荷失败测试

- [ ] 新增 `IFD2` 构建/解析 round-trip、篡改校验、非法键/版本测试。
- [ ] 保留现有 `IFD` 构建和解析断言不变。
- [ ] 渲染器测试传入已发布岗位配置，解码 PNG 后必须得到模板键/版本 + 岗位键/版本。
- [ ] 绑定的模板 ID/版本不一致时拒绝渲染。
- [ ] Run: 领域和 renderer 两个测试文件，确认新契约不存在而失败。

### Task 2: 领域与渲染实现

- [ ] 新增 `build_template_profile_payload` / `parse_template_profile_payload`，校验和覆盖四段身份。
- [ ] `TemplatePrintRenderer.render` 和 `compose_imposition` 接受可选岗位配置；传入时使用 IFD2，未传入继续 IFD。
- [ ] 含岗位配置的产物文件名加入岗位键和版本，避免不同岗位覆盖同一模板产物。
- [ ] 不修改现有识别流程；下一任务再让识别结果承载岗位配置身份。

### Task 3: 局部验证

- [ ] Run: `.venv\\Scripts\\python.exe -m pytest tests/unit/test_templates_domain_ds.py tests/adapters/test_template_print_renderer_ds.py -q`。
- [ ] Run: Ruff 与相关 mypy。
- [ ] 不运行种子、API、前端或完整测试。

