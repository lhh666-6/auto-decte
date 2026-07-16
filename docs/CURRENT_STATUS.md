# 当前项目状态

最后更新：2026-07-16

## 状态依据

| 项目 | 当前值 |
|---|---|
| 集成分支 | `modular-architecture` |
| 本轮收尾前 HEAD | `08daef7 docs: record teammate review and remaining work` |
| 远程同步 | `HEAD` 与 `origin/modular-architecture` 一致 |
| 工作树 | 收尾开始时干净，无未提交业务代码 |
| Python 测试 | `185 passed` |
| Ruff | 全部通过 |
| mypy | 124 个源文件无问题 |
| 前端测试 | 6 个测试文件，`34 passed` |
| 前端构建 | TypeScript 类型检查与 Web 生产构建通过 |
| 浏览器人工验收 | 沿用 2026-07-15 队友记录；本轮拉取后未完整重跑 |

以上自动化结果来自 2026-07-16 对队友提交和旧库兼容修复的复测。当前收尾只修改文档，不修改业务代码。

## 整体状态

项目已经从 Streamlit 工程原型演进为 Windows 本地优先的模块化单体 Demo。模板设计、纸质表单识别基础、图片导入、人工审核、版本审计和主数据管理已经形成可运行链路；React Web 前端已替换主要占位页面，并保留未来由 Tauri 封装同一前端的架构方向。

当前阶段已经冻结，没有正在编辑的功能模块。产品闭环的主要缺口是模板化 XLSX 导出与重导中心，其次是模板包/纸张实例、生产任务 Handler、审核高级工具和桌面壳。

## 已完成模块

| 模块 | 已完成能力 | 主要证据 |
|---|---|---|
| 基础架构 | 模块化单体、领域/应用/适配器分层、SQLite、UoW、配置与组合根 | `app/domain/`、`app/application/`、`app/modules/`、`app/services/container.py` |
| 身份与权限 | 5 个角色、显式权限矩阵、默认最小权限 `local-operator/OPERATOR` | `app/modules/identity_access/`、`7293ea3` |
| 图片与证据 | 受控上传、原图 SHA-256 去重、不可变证据、派生图允许重复、失败回滚 | `app/api/routers/imports_ds.py`、`app/adapters/storage/`、`bd54ab3` |
| 模板中心 | 模板库、草稿、只读发布版本、复制调优、预检、发布、退役、名称与用途 | `app/api/routers/templates_ds.py`、`frontend/apps/web/src/TemplateLibrary_ds.tsx` |
| 模板设计器 | A4/A5 画布、字段选择、拖动、缩放、键盘移动、属性编辑和保护区 | `TemplateCanvasEditor_ds.tsx`、`FieldInspector_ds.tsx`、`a8374b6` |
| 企业模板 | 4 个工资/生产模板幂等 seed，包含字段、规则、导出目标和 PNG/PDF | `app/modules/templates/seed_templates_ds.py`、`3ed353c` |
| 识别基础 | 模板 QR、ArUco 10/11/12/13、标准画布、字段裁切、RecognitionAttempt、OCR/OMR 候选 | `app/application/recognize_forms.py`、`app/adapters/recognition/` |
| 审核工作台 | 左图右表、真实队列、字段联动、草稿、Lease、退回、作废、人工分类、原子确认并领取下一张 | `app/modules/review/`、`app/api/routers/review_ds.py`、`frontend/apps/web/src/App.tsx`、`a20e295` |
| 主数据 | 员工、工单、产品、工序 CRUD、搜索、乐观版本、停用/恢复、审计、审核字段下拉联动 | `app/modules/master_data/`、`MasterDataCenter_ds.tsx`、`5b9de49` |
| 任务基础 | SQLite 任务、幂等键、状态机、事件序列、SSE、重启中断恢复 | `app/modules/tasks/`、`app/infrastructure/tasks/`、`app/api/routers/tasks_ds.py` |
| 审计与运维 | RecordVersion、AuditEvent、备份恢复、完整性检查、结构化日志骨架 | `app/infrastructure/backup/`、`app/modules/audit/` |
| 导出基础 | 同步四工作表 XLSX、批次哈希、`(form_id, record_version)`、旧文件保留、`REEXPORT_REQUIRED` | `app/application/export_forms.py`、`app/adapters/export/xlsx.py`、`tests/integration/test_xlsx_export.py` |

## 正在开发模块

无。本阶段已经结束，工作树没有未提交业务代码。

下一项计划任务为“模板化导出与重导闭环”，范围见 [NEXT_TASK.md](NEXT_TASK.md)。在该任务正式开始前，不应继续扩展模板、识别、审核或主数据模块。

## 已知问题与未完成项

1. **导出中心尚未产品化**：没有导出 API Router、React 导出中心、导出预览、受控下载、模板映射驱动、持久化 `XLSX_EXPORT` Handler、完整批次快照和重导替代关系。
2. **XLSX 公式注入防护未验收**：当前导出器直接写入字段值，尚无针对 `= + - @` 开头文本的明确转义测试。
3. **生产任务消费未闭环**：任务状态机和 SSE 已有，但 `FORM_IMPORT`、`FORM_RECOGNITION`、`XLSX_EXPORT` 尚未全部由独立生产 Worker/Handler 消费。
4. **模板包与纸张实例未实现**：缺少安全 ZIP 导入/导出、manifest/hash 校验、打印批次和每张纸唯一 `sheet_instance_id`。
5. **审核高级工具未完成**：缺少显式上一张/下一张、跨筛选队列快照、图片缩放/旋转/复位、字段裁切详情、完整三阶段规则面板和导出影响 UI。
6. **中文 OCR 未接入**：日期、班次、姓名等文本字段仍以人工录入为主，系统不会伪造识别结果。
7. **旧库内置模板冲突需要人工决策**：如果旧库已有同名 V1 模板但内容不同，应用会保留旧模板、记录警告并继续启动，不会自动覆盖或自动安装其余 seed。后续需通过新版本或显式迁移解决。
8. **桌面化尚为骨架**：Tauri v2、File/Camera/Scanner/Audio Ports、Windows 安装包和真实设备接入未完成。
9. **人工验收仍不充分**：本轮没有在最新拉取状态下重新走完整浏览器闭环；40–60 张真实企业样表的量化验收也尚未完成。

## 继续工作前

```powershell
git fetch origin
git switch modular-architecture
git pull --ff-only origin modular-architecture
git status --short
```

预期 `git status --short` 无输出。继续开发前还应阅读 [NEXT_TASK.md](NEXT_TASK.md)、[DECISIONS.md](DECISIONS.md) 和最新 [handoff](handoffs/2026-07-16-template-review-master-data.md)。
