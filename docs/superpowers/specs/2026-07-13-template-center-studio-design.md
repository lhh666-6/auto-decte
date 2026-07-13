# 模板中心与可视化设计器设计

状态：已确认，待文档审阅后进入实现计划。  
日期：2026-07-13  
适用：React Web Shell、未来 Tauri Desktop Shell、FastAPI 模块化单体。

## 目标

将当前“填写模板键后创建草稿”的技术配置页，改为可供管理员实际使用的模板中心：

```text
模板选择
→ 已发布模板只读预览
→ 基于模板调优
→ 新草稿版本
→ 画布和字段配置
→ 发布预检
→ 不可变发布版本
→ 打印与导入识别
```

该模块服务于表单管理员，不向现场工人暴露模板配置、识别阈值或导出映射。

## 用户体验与页面边界

### 模板中心（首屏）

打开“模板与字段”必须首先显示模板选择界面，不得直接显示空白参数表。首版展示：

| 模板键 | 名称 | 适用场景 |
|---|---|---|
| `PAYROLL_HOURLY` | 计时工资单 | 计时工、叉车人员 |
| `PAYROLL_STANDARD_PIECE` | 标准计件单 | 炭化、蒸煮、装架等分类单价岗位 |
| `PAYROLL_FIXED_PRODUCTION_GRID` | 固定生产明细单 | 热压、开片/光刨等固定明细岗位 |
| `PAYROLL_EQUIPMENT_PROCESS` | 设备工序单 | 油炉、过程检查和扣款岗位 |

每张模板卡片展示名称、模板键、页面规格、当前发布版本、字段数和简短用途。首屏同时提供：模板分类筛选、搜索、空白模板创建和模板包导入入口。没有模板数据时显示清晰的空状态与“创建空白模板”动作。

### 已发布模板预览

选择已发布模板进入只读预览，不自动创建版本。预览包括纸张缩略图、字段清单、识别策略摘要、版本历史、打印文件和模板包下载。

唯一的修改入口是“基于此模板调优”。该动作克隆出新的 `DRAFT` 版本，保留 `parent_version_id`；原发布版本、历史打印件和已绑定表单都不改变。

### 调优设计器

设计器采用三栏布局：

```text
组件与图层栏 | 标准 A4/A5 画布 | 当前字段属性与规则
```

- 左栏：固定文字、单行字段、数字格、OMR、固定表格行；并显示二维码、纸张实例码和定位角标等锁定组件。
- 中栏：以标准坐标系渲染可打印表单。点击字段选中，拖动改变位置，拉伸改变区域大小；显示网格、打印安全区和不可覆盖区域。
- 右栏：编辑 `field_key`、显示名、数据/输入类型、识别引擎、预填阈值、范围/必填/主数据/跨字段规则和导出键。

编辑状态必须显著显示“草稿版本”。不允许用户在画布中拖动或覆盖模板 QR、`SHEET` 实例码、四个 ArUco 角标和页面边缘安全区。

## 领域与 API 设计

现有 `TemplateVersion`、`FieldDefinition`、预检、发布、打印产物和模板仓储继续作为唯一事实源。React 不能以本地状态替代模板版本。

新增或补齐的 API 契约：

```text
GET  /api/v1/templates                         模板库摘要
GET  /api/v1/templates/{template_key}/versions 版本历史
GET  /api/v1/template-versions/{version_id}     只读版本详情
POST /api/v1/template-versions/{version_id}/clone
POST /api/v1/template-versions/{version_id}/fields
PATCH /api/v1/template-versions/{version_id}/fields/{field_key}
DELETE /api/v1/template-versions/{version_id}/fields/{field_key}
POST /api/v1/template-versions/{version_id}/preflight
POST /api/v1/template-versions/{version_id}/publish
```

`PATCH` 与字段移动必须只允许 `DRAFT`；请求携带版本或更新标记，发生并发冲突时返回 `409 TEMPLATE_VERSION_CONFLICT`。发布和模板包导入仍使用完整哈希、白名单与审计要求。

## 状态与错误处理

| 情况 | UI 行为 |
|---|---|
| 无权限 | 不显示危险动作；后端返回权限错误时展示可理解的权限提示 |
| 发布版本 | 所有画布与属性只读，显示“基于此模板调优” |
| 预检失败 | 列出定位标记、QR、安全区、字段重叠、类型兼容或规则引用问题；定位到对应画布区域 |
| 并发冲突 | 保留本地未保存编辑，要求刷新或复制为新草稿，绝不静默覆盖 |
| 导入模板包失败 | 显示 ZIP/哈希/schema/版本冲突原因，不创建半成品版本 |
| 画布操作非法 | 阻止落点并解释锁定区或打印安全区原因 |

## 前端边界

建议 Feature 目录：

```text
frontend/features/template-studio/
  TemplateLibraryPage.tsx
  TemplatePreviewPage.tsx
  TemplateCanvasEditor.tsx
  FieldInspector.tsx
  TemplateLibraryCard.tsx
  template-studio.css
  useTemplateDraft.ts
```

Feature 只能通过 `@form-detection/api-client` 调用 API，并只使用共享设计系统和 Shell Ports。不得直接访问 SQLite、服务器证据路径、本地文件绝对路径或 Tauri API。

## 视觉原则

沿用已确认的深海蓝工业控制台基线：页面背景 `#E9EEF5`、卡片白底、焦点蓝 `#2563EB`、正常绿 `#16A34A`、警告黄 `#F59E0B`。模板中心必须比审核台更强调层级与留白；不使用当前大面积空白的参数面板。画布保持纸张比例，属性仅在选中字段后显示，空选择状态显示快捷开始说明。

## 验收条件

1. 打开模板中心首先看到模板库，四类种子模板可选择。
2. 发布模板只读；点击调优才创建带父版本关系的草稿。
3. 草稿中字段可选中、移动、缩放和编辑属性；受保护区域不可修改。
4. 字段坐标、字段类型、识别策略和规则通过 API 持久化，刷新后不丢失。
5. 预检失败能定位原因；通过后才允许发布。
6. 发布产生不可变版本与打印产物；历史表单不切换版本。
7. 浏览器、API、模板领域测试和前端类型检查通过。

## 首版不支持

- 多页模板；
- 动态新增生产明细行；
- 已发布版本原地编辑；
- 客户端直接读取或写入本地路径；
- 绕过 API 的模板包/打印件访问。
