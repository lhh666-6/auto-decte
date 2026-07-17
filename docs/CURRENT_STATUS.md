# 当前项目状态

最后更新：2026-07-17

## 2026-07-17 前端重建交接

人工试用和外部界面方案已经完成归纳，下一开发方向正式确定为“工业表单前端重建与交互优化”。完整执行顺序见 [前端重建实施计划](superpowers/plans/2026-07-17-frontend-rebuild-implementation.md)，当前界面真实行为与不可破坏语义见 [前端交互闭环说明](FRONTEND_INTERACTION_GUIDE.md)。后续队友只需读取这两份文件、本状态文件、`NEXT_TASK.md` 和 `DECISIONS.md`，然后按计划逐项完成，无需扫描整个仓库。

产品规格唯一依据为用户提供的 `frontend_rebuild_summary.md`。开发重点固定为：先完成核心双栏审核闭环，再建立统一应用外壳和路由，最后压缩模板、基础数据和导出模块；不得加入原文没有批准的产品功能。

本轮只更新文档，没有修改业务代码或重新运行自动化测试。最近功能基线仍为 `35c1243 fix(frontend): support exported form corrections`；文档提交推送后，队友从 `origin/modular-architecture` 拉取继续开发。

已确认的实施边界：前端可以利用现有任务查询接口原地显示识别进度；但“待重新拍照表单上传新照片并永久保存新旧替换关系”缺少生产 API，不能由纯前端伪造。该缺口已在实施计划和 `NEXT_TASK.md` 中设为硬阻塞。

## 状态依据

| 项目 | 当前值 |
|---|---|
| 集成分支 | `modular-architecture` |
| 当前 HEAD | `35c1243 fix(frontend): support exported form corrections` |
| 远程同步 | 本地 `modular-architecture` 领先 `origin/modular-architecture` 27 个提交，尚未推送 |
| 工作树 | 本轮文档更新前干净，无未提交业务代码 |
| Python 测试 | 最近全量 `264 passed`；本轮 QR/模板定向验证 `26 passed` |
| Ruff | 全部通过 |
| mypy | 128 个源文件无问题 |
| 前端测试 | `53 passed` |
| 前端构建 | TypeScript 类型检查与 Web 生产构建通过 |
| 浏览器人工验收 | 已启动真实 Web/API 链路并进行部分试用；发现权限与纸面模板产品适配问题，尚未完成最终验收 |

以上全量自动化结果来自本轮功能收尾验证；`26 passed` 是 2026-07-17 对二维码生成、打印导出、精确版本绑定、图片导入和模板 API 的定向复测。当前工作只记录人工试用发现，不修改业务代码。

## 整体状态

项目已经从 Streamlit 工程原型演进为 Windows 本地优先的模块化单体 Demo。模板设计、纸质表单识别基础、图片导入、人工审核、版本审计和主数据管理已经形成可运行链路；React Web 前端已替换主要占位页面，并保留未来由 Tauri 封装同一前端的架构方向。

模板化 XLSX 导出与重导中心已经完成。当前阶段转为人工验证和问题发现：先验证真实工厂纸表、打印、拍照、识别与审核体验，再决定模板产品化改造的实施顺序。此阶段不新增功能。

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
| 导出闭环 | 模板映射预览、持久化 `XLSX_EXPORT` 任务、批次历史、受控下载、公式注入防护、旧文件保留、`REEXPORT_REQUIRED` 与显式重导替代关系 | `app/api/routers/exports_ds.py`、`app/modules/reporting/handler_ds.py`、`frontend/apps/web/src/ExportCenter_ds.tsx`、`tests/api/test_exports_api_ds.py` |

## 正在开发模块

无。当前只进行人工验证、样本收集和问题记录，工作树没有未提交业务代码。

当前目标为“人工验证与问题收集”，范围见 [NEXT_TASK.md](NEXT_TASK.md)。在形成真实样本证据和明确实施优先级前，不扩展模板、识别、审核或主数据模块。

## 2026-07-17 人工试用发现

1. **本地权限与产品入口冲突**：系统没有登录界面，但默认 `OPERATOR` 会阻止图片导入和模板创建，用户只能通过临时 ADMIN 配置继续试用。需要在未来明确“本地单用户完整能力”与“多用户部署权限矩阵”的产品边界；当前不改权限实现。
2. **现有纸面模板过于通用**：自由手写区域和通用字段过多，不符合工厂希望减少工人自由发挥、提高格式化程度和降低识别难度的目标。
3. **纸张尺寸模型过窄**：当前设计器和 API 只提供 A4/A5；真实表格可能是尺寸不固定的横条，需要支持任意毫米宽高、横竖方向和多联裁切。
4. **模板搭建粒度不合适**：需要数字方格、单选方块、姓名/签名线、固定明细行、异常短说明、二维码安全区等受约束小模块，并采用毫米网格吸附；不应退化为完全自由绘图工具。
5. **人员核验规则未产品化**：工号暂按纯数字逐格识别并与员工库匹配，姓名只供人工对照；工号不存在时应允许保存复核，但禁止正式工资导出。
6. **现场识别效果尚无证据**：自动测试证明了干净样张的二维码闭环，但还没有覆盖不同打印机、手机、光线、折痕、缩放和二维码污损的真实工厂样本。
7. **原始工资表应作为产品依据**：后续母版需从根目录现有计时、计件和复杂生产明细工作簿提炼，不以当前演示模板的视觉结构为最终业务结构。

## 已知问题与未完成项

1. ~~**导出中心尚未产品化**~~：已完成导出 API、React 导出中心、预览、受控下载、持久化任务、批次快照和重导替代关系。
2. ~~**XLSX 公式注入防护未验收**~~：已增加 `= + - @` 开头文本的防护与测试。
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
