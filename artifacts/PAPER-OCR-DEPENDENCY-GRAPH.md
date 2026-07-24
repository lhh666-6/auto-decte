# Paper OCR 退役 — 全量依赖图审计报告

Branch: `modular-architecture` | SHA: `b1d5cd6d` | Alembic: `036`

---

## 1. 核心耦合图

```
ElectronicFormDefinitionVersion (新V1)
    │
    ├─ template_version_id ──→ TemplateVersionRow (旧模板表)
    ├─ job_profile_version_id ──→ JobProfileVersionRow (旧岗位配置表)
    │
    └─ 发布验证依赖: electronic_definitions_ds.py
         → template_repository_ds.py
         → templates_ds.py (旧 Domain)
```

**这是最高风险耦合**: 新电子表单通过 FK 绑定旧模板体系。必须先解耦此关系才能大规模删除。

---

## 2. 数据库状态

### Migration 027 已执行（表已重命名）

| 旧表名 | 新表名 (legacy_archive_*) | 数据行 |
|--------|--------------------------|--------|
| recognition_attempts | legacy_archive_recognition_attempts | 0 |
| evidence_files | legacy_archive_evidence_files | 2 |
| ai_reviews | legacy_archive_ai_reviews | 1 |
| review_leases | legacy_archive_review_leases | 0 |
| review_drafts | legacy_archive_review_drafts | 0 |
| tasks | legacy_archive_tasks | 0 |
| task_events | legacy_archive_task_events | 0 |
| export_batches | legacy_archive_export_batches | 1 |

### 仍在活跃使用的表

| 表名 | 行数 | 说明 |
|------|------|------|
| template_versions | 30 | V1 模板版本（活跃） |
| template_metadata | 20 | 模板元数据 |
| template_fields | 708 | 模板字段定义 |
| template_artifacts | 80 | 模板渲染产物 |
| job_profile_versions | 10 | 岗位配置版本 |
| forms | 2 | 纸质表单主表 |
| form_fields | 0 | 表单字段表 |
| record_versions | 0 | 记录版本 |

### 关键发现

**迁移 027 已将 8 个旧 OCR 表重命名为 legacy_archive_*，但代码未同步清理**:
- `SqliteTaskStore` 仍引用 `TaskRow` → 对应表名 `tasks` (已变更为 `legacy_archive_tasks`)
- `SqlAlchemyReviewLeaseRepository` 仍引用 `ReviewLeaseRow` → 对应表名 `review_leases` (已变更)
- `SqlAlchemyFormRepository` 级联删除路径中引用 8 个已退役表
- **风险**: 如果 TaskService/ReviewFacade 被调用任何 CRUD 方法，会直接 Table Not Found 报错

---

## 3. 后端文件分类

### A 类 — 纯旧 OCR（可删除）: 12 文件

```
app/application/recognize_forms.py          OCR 识别主链
app/adapters/recognition/candidate.py      识别候选
app/adapters/recognition/digits.py          数字框识别
app/adapters/recognition/omr.py             OMR 复选框
app/api/routers/imports_ds.py              图片导入 API (未挂载)
app/api/routers/classification_ds.py       分类 API (未挂载)
app/ui/pages/classification.py            Streamlit 分类页
app/ui/pages/import_page.py             Streamlit 导入页
app/tools/build_paper_acceptance_pack_ds.py 打包工具
app/adapters/templates/print_renderer_ds.py 纸张打印渲染
app/modules/templates/payroll_profiles_ds.py 旧薪资配置
```

### B 类 — 新 V1（保留）: 50+ 文件

```
app/modules/bamboo_process/*              全部
app/modules/electronic_forms/*            全部
app/modules/identity_access/*              全部
app/modules/payroll_rules/*                全部
app/modules/report_templates/*            全部
app/application/bamboo_operations_ds.py    全部
app/api/routers/mobile_*.py               全部 (5 files)
app/api/routers/plant_workspace_ds.py      
app/api/routers/finance_workspace_ds.py    
app/api/routers/admin_console_ds.py        
app/api/routers/web_auth_ds.py             
app/adapters/database/bamboo_process_repository_ds.py
app/adapters/database/mobile_identity_repository_ds.py
app/adapters/export/xlsx.py                
app/modules/evidence/facade_ds.py          
```

### C 类 — 混合职责（需拆分）: 15 文件

| 文件 | 混合内容 |
|------|---------|
| `app/domain/templates_ds.py` | 旧 OCR 概念 (PaperEntryMode,RecognitionMode,PrintImposition) + 共享概念 (TemplateVersion,PayrollJobProfileVersion,CoreLayoutKind) |
| `app/adapters/database/template_repository_ds.py` | 被新 electronic_definitions_ds.py 引用进行发布验证 |
| `app/adapters/recognition/opencv.py` | 被新 templates/facade_ds.py 用于 QR/field crop + 旧 OCR recognize_forms.py |
| `app/application/electronic_definitions_ds.py` | 新电子表单发布验证桥接到旧 template_repository |
| `app/application/import_forms.py` | 被新 EvidenceFacade 消费 + 旧 OCR UI/router |
| `app/application/export_forms.py` | 引用 TemplateVersion 用于新旧导出 |
| `app/application/template_versions_ds.py` | 管理被新系统引用的模板数据 |
| `app/application/job_profiles_ds.py` | 管理被新系统引用的岗位配置 |
| `app/modules/templates/facade_ds.py` | 包装旧 opencv 用于 QR/filed crop |
| `app/modules/templates/core_payroll_layouts_ds.py` | 使用旧 domain 类的新 V2 布局 |
| `app/modules/templates/seed_templates_ds.py` | 安装当前 V1 模板（含 "legacy" 命名误导） |
| `app/modules/recognition/facade_ds.py` | 包装旧 RecognizeForms |
| `app/modules/review/facade_ds.py` | 引用 TemplateVersion |
| `app/modules/reporting/facade_ds.py` | 引用 template_repository |
| `app/services/container.py` | 创建新旧两者服务 + 安装旧 seed |

---

## 4. 前端文件分类

### 可删除: 14 文件（旧 Template Studio）

```
frontend/apps/web/src/TemplateStudio_ds.tsx
frontend/apps/web/src/TemplateStudio_ds.test.tsx
frontend/apps/web/src/TemplateLibrary_ds.tsx
frontend/apps/web/src/TemplateLibrary_ds.test.tsx
frontend/apps/web/src/TemplatePreview_ds.tsx
frontend/apps/web/src/TemplatePreview_ds.test.tsx
frontend/apps/web/src/TemplateCanvasEditor_ds.tsx
frontend/apps/web/src/TemplateCanvasEditor_ds.test.tsx
frontend/apps/web/src/FieldInspector_ds.tsx
frontend/apps/web/src/FieldInspector_ds.test.tsx
frontend/apps/web/src/template-studio-model.ts
frontend/apps/web/src/template-studio-model.test.ts
frontend/apps/web/src/template-studio-state.ts
frontend/apps/web/src/template-studio-state.test.ts
```

### API Client 清理

**删除**: `frontend/packages/api-client/src/templates_ds.ts` (全部)
**删除**: `frontend/packages/api-client/src/imports_ds.ts` (全部)
**保留**: `frontend/packages/api-client/src/review-workbench.ts` (仍活跃)
**更新**: `index_ds.ts` 移除旧 OCR re-export

### CSS 清理: ~145 行

`styles.css` 中 `.template-studio`, `.template-library-*`, `.template-preview-*`, `.template-canvas-*`, `.field-inspector-*` 相关样式

### 导航/路由

- `router.tsx`: 无旧 OCR 路由 ✓
- `WorkspaceShell.tsx`: 无旧 OCR 导航 ✓
- Review Workbench 仍活跃（ClassificationStage, RecaptureStage）— **不删除**

---

## 5. Service Container 清理清单

### 可删除的服务注册

```
recognize_forms        → 纯 OCR
template_renderer      → 纸张打印
imports               → 图片导入（EvidenceFacade 也引用，需迁移）
recognition_facade     → 包装旧 OCR
templates_facade       → 需先迁移 opencv QR/crop 依赖
```

### 需保留的服务

```
bamboo_operations, bamboo_process, mobile_identity, master_data,
fact_records, electronic_definitions, electronic_integration,
evidence_storage, tasks, task_store, export_handler,
reporting, review_facade, review_leases, review_repository,
payroll_rules, report_templates, managed_forms, ai_reviews
```

---

## 6. 推荐删除顺序

```
Phase 1: 解耦（关键）
├─ 审计 ElectronicFormDefinitionVersion.template_version_id 的实际业务语义
├─ 确认 ManagedFormVersion 是否已可替代 TemplateVersion
├─ 如果已可替代 → 移除 FK，让 electronic_definitions 不依赖 template_repository
└─ 如果未替代 → 先完成 ManagedFormVersion 迁移

Phase 2: 前端清理（低风险）
├─ 删除 14 个 Template Studio 文件
├─ 删除 styles.css 中 ~145 行模板样式
├─ 删除 API Client 中 templates_ds.ts + imports_ds.ts
└─ 更新 index_ds.ts re-export

Phase 3: 后端 A 类删除（中风险）
├─ 删除 12 个纯 OCR 文件
├─ 删除 container.py 中的旧服务注册
├─ 删除 seed 中的旧模板 seed（需确认新系统不依赖）
└─ 更新 container.py 中的 import

Phase 4: 代码级清理（中风险）
├─ 清理 repositories.py 中 8 个已退役表的 Row 引用
├─ 修复 SqliteTaskStore → 迁移到新表或彻底移除
├─ 修复 SqlAlchemyReviewLeaseRepository → 迁移或移除
└─ 清理 ensure_auto_created_schema_compatibility 中的旧表操作

Phase 5: 数据库退役 Migration（低风险，因为表已重命名）
├─ 创建 Migration 037: DROP 8 个 legacy_archive_* 表
├─ 删除 models.py 中 8 个旧 Row 类定义
└─ 清理 migration.py 中的 LEGACY_RETIREMENT_TABLES 引用

Phase 6: 依赖清理
├─ 检查 opencv-python-headless 是否仍有引用
├─ 检查 numpy 是否有独立于 opencv 的引用
└─ 移除真正无引用的依赖
```

---

## 7. 风险矩阵

| 风险等级 | 项 | 影响 |
|---------|-----|------|
| **严重** | ElectronicFormDefinitionVersion.template_version_id FK | 新电子表单绑定旧模板，不解耦则无法删除 |
| **高** | SqliteTaskStore 引用已重命名的表 | 调用即崩溃（但当前路径未触发？） |
| **高** | repositories.py 级联引用 8 个退役表 | delete_form 路径会崩溃 |
| **中** | opencv.py 被新 templates/facade 引用 | 不能直接删除整个 opencv 模块 |
| **中** | seed 函数名含 "legacy" 但安装的是 V1 模板 | 命名误导 |
| **低** | legacy_archive_* 表有少量残留数据 | 无业务影响 |
| **低** | styles.css 中 review-workbench 样式与模板样式混合 | 需精确删除 |
