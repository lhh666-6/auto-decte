# 开发进度与接力记录

> 本文件是两位 Codex 协作时的唯一明文接力状态。每次功能提交必须同步更新。

## P0 项目初始化

- 状态：已完成并推送
- 负责人：开发者 A（仓库所有者）
- 分支：`phase-0-bootstrap`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 建立 Python 3.11 项目配置和开发依赖
  - 建立环境配置、Streamlit 入口和测试框架
  - 建立 Git 忽略规则和协作说明
- 未完成：无
- 验证命令：`python -m pytest -v`；`python -m ruff check .`
- 验证结果：`1 passed`；Ruff `All checks passed!`；mypy `Success: no issues found in 5 source files`
- 最新提交：`d8d2b6c`
- 已知问题：无；已使用 GitHub SSH 推送
- 下一位操作：P0 合并后从最新 `main` 创建 `phase-1-manual-loop`

## P1 人工闭环

- 状态：已完成并推送
- 负责人：开发者 A（仓库所有者）
- 分支：`phase-1-manual-loop`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 领域实体、状态枚举和 Adapter 协议
  - SQLite 表单与不可变版本持久化
  - 原始图片 SHA-256、重复检测和只增证据存储
  - E99/自由说明/非常规更正/争议录音触发校验
  - 人工确认、更正、乐观版本检查和审计事件
  - 可操作的 Streamlit 图片导入与人工复核页面
- 未完成：无；仓库创建较晚，本阶段随已验证的 `main` 一并集成
- 验证命令：
  - `uv run python -m pytest -q`
  - `uv run python -m ruff check .`
  - `uv run python -m mypy app config`
  - `uv run python -c "from streamlit.testing.v1 import AppTest; ..."`
- 验证结果：`14 passed`；Ruff 全部通过；mypy 检查 22 个源文件无问题；Streamlit 无异常并显示“批量导入/人工复核”
- 最新提交：`71e8001`
- 已知问题：无；远程阶段分支 `phase-1-manual-loop` 已保留
- 下一位操作：已完成；后续阶段从最新 `main` 或 P6 集成分支继续

## P2 查询与导出

- 状态：已完成并推送
- 负责人：开发者 A（仓库所有者）
- 分支：`phase-2-query-export`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 基于 SQLite JSON 字段的表单/员工/工单组合精确筛选
  - 表单版本、证据和审计事件完整追溯
  - 正式数据、异常与复核、汇总、导出说明四工作表 XLSX
  - ExportBatch、文件 SHA-256、表单/版本反查标识
  - 已导出记录更正后自动标记 `REEXPORT_REQUIRED`
  - 唯一文件名导出，不覆盖旧 XLSX
  - Streamlit 查询追溯与导出页面
- 未完成：无；仓库创建较晚，本阶段随已验证的 `main` 一并集成
- 验证命令：`uv run python -m pytest -q`；`uv run python -m ruff check .`；`uv run python -m mypy app config`；Streamlit AppTest
- 验证结果：`18 passed`；Ruff 全部通过；mypy 检查 28 个源文件无问题；四个 UI 标签页加载无异常
- 最新提交：`943a174`
- 已知问题：无；远程阶段分支 `phase-2-query-export` 已保留
- 下一位操作：已完成；P3 已在独立分支实现并进入 P6 集成

## P3 图像与识别

- 状态：功能实现完成并通过合成测试，待真实样张指标验收
- 负责人：开发者 B（当前 Codex 会话代执行）
- 分支：`phase-3-recognition`
- 开始时间：2026-07-12
- 完成时间：功能代码 2026-07-12；真实样张验收未完成
- 已完成：
  - 模糊、过暗、强反光/空白图像质量检测与原因码
  - 透视校正和模板坐标字段裁切
  - 二维码优先模板分类与无二维码人工分类队列
  - 人工重新分类及 before/after/reason 审计事件
  - 单格数字 OpenCV 模板候选与空白保护
  - OMR 勾选、未勾选和歧义区间识别
  - FormField、RecognitionAttempt、字段裁切证据持久化
  - 识别 Attempt 只增保存，不覆盖人工确认版本
  - 追溯页展示识别 Attempt，Streamlit 图像分类页面
- 未完成：
  - 使用企业 30–50 张脱敏真实样张测量分类率、单数字准确率和整单正确率
  - 根据真实表单冻结三套模板坐标和定位点
- 验证命令：`uv run python -m pytest -q`；`uv run python -m ruff check .`；`uv run python -m mypy app config`；Streamlit AppTest
- 验证结果：`39 passed`；Ruff 全部通过；mypy 检查 37 个源文件无问题；六个 UI 标签页加载无异常
- 最新提交：`85eed55`
- 已知问题：当前数字识别为轻量合成字体基线，未达到真实生产样张准确率声明条件
- 下一位操作：提供三类模板和 30–50 张脱敏样张，在本分支补充 golden fixtures 与准确率报告

## P4 规则与审计

- 状态：已完成开发者 A 部分并推送，待开发者 B 审查
- 负责人：开发者 A 主导、开发者 B 审查
- 分支：`phase-4-rules-audit`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 必填、取值范围、数量闭合规则
  - 员工/工单主数据有效性规则
  - 重复表单、当前版本、重新导出和导出映射规则
  - 字段级错误码、严重性和中文失败原因
  - 导入、确认、更正和导出的审计完整性测试
  - Streamlit 规则异常页面
- 未完成：开发者 B 交叉审查；P3 接入后补充分类型/识别审计事件
- 验证命令：`uv run python -m pytest -q`；`uv run python -m ruff check .`；`uv run python -m mypy app config`；Streamlit AppTest
- 验证结果：`29 passed`；Ruff 全部通过；mypy 检查 30 个源文件无问题；五个 UI 标签页加载无异常
- 最新提交：`f6da6ec`
- 已知问题：远程阶段分支 `phase-4-rules-audit` 已保留；P3 审计覆盖已在集成分支补充
- 下一位操作：P6 已覆盖分类、识别、确认和导出组合审计

## P5 AI 与向量

- 状态：Demo 功能已完成并推送，已进入 P6 集成审查
- 负责人：开发者 B 主导、开发者 A 审查（当前 Codex 会话代执行）
- 分支：`phase-5-ai-vector`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 默认关闭且不发起外部请求的 AI Adapter
  - 严格结构化 AIReview/AISuggestion 合约
  - 证据列表非空、置信度范围和强制人工确认校验
  - 可注入 Provider，只接受严格 JSON 且校验 form_id
  - AI 建议独立持久化，不覆盖 RecordVersion
  - AI 建议审计事件与 AI 关闭端到端导出测试
  - 本地字符/二元组余弦相似检索，只返回引用
  - Streamlit AI 审查与相似异常检索页面
- 未完成：
  - 企业授权后的真实外部 AI API 配置与脱敏策略验收
  - 可选录音转写 Provider 和真实相似案例评估
- 验证命令：`uv run python -m pytest -q`；`uv run python -m ruff check .`；`uv run python -m mypy app config`；Streamlit AppTest
- 验证结果：`38 passed`；Ruff 全部通过；mypy 检查 38 个源文件无问题；六个 UI 标签页加载无异常
- 最新提交：`db9b7c1`
- 已知问题：本地向量索引为进程内 Demo 基线；外部 AI 默认关闭且未配置任何密钥
- 下一位操作：开发者 A 审查安全边界；未取得企业授权前保持 `FORM_DEMO_AI_ENABLED=false`

## P6 联调验收

- 状态：自动化联调完成，真实样张与现场指标待验收
- 负责人：两位开发者共同完成（当前 Codex 会话完成自动化部分）
- 分支：`phase-6-acceptance`
- 开始时间：2026-07-12
- 完成时间：自动化联调 2026-07-12；现场验收未完成
- 已完成：
  - 合并 P3 图像识别与 P5 AI/向量两条独立分支
  - 跨模块端到端验收：分类、识别、规则、确认、AI 关闭、检索、导出、追溯
  - README 启动、备份恢复、安全和 GitHub 接力说明
  - `docs/acceptance-report.md` 自动化证据与现场缺口报告
- 未完成：
  - 30–50 张脱敏真实样张技术指标
  - 100–300 张现场试点和人工基线对比
  - 企业 XLSX 模板、三种表单坐标和录音授权验收
- 验证命令：提交前运行全量 pytest、Ruff、mypy 和 Streamlit AppTest
- 验证结果：`49 passed`；Ruff 全部通过；mypy 检查 45 个源文件无问题；七个 UI 标签页加载无异常
- 最新提交：`6e53917`
- 已知问题：缺少源需求第 15 节列出的真实样张、金标准、主数据和企业模板
- 下一位操作：提供验收输入后补充受控 golden 数据集与真实指标，不得用合成测试替代

## P7 模块化架构实施

- 状态：已完成
- 负责人：Deepseek AI（当前会话）
- 分支：`modular-architecture`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 所有文件加 `_ds` 后缀命名统一
  - 建立 12 个模块目录和 Facade 入口（forms, evidence, recognition, review, rules,
    search, reporting, audit, tasks, identity_access, master_data, templates）
  - SQLite 连接工厂（WAL/外键/busy_timeout）和 UnitOfWork 事务边界
  - 身份角色权限：ADMIN/OPERATOR/REVIEWER/FINANCE/AUDITOR + 权限矩阵
  - ReviewLease 审核锁（获取/续租/过期/强制释放/审计事件）
  - Task 状态机（PENDING→RUNNING→SUCCEEDED/FAILED）+ 幂等键 + 重启恢复
  - FastAPI 骨架（/health/live, /health/ready, /api/v1/me）
  - API 路由：审核锁、确认（带 expected_version）、任务（SSE 进度推送）
  - Problem Details 错误格式化、request_id 全链路追踪
  - Alembic 迁移基线（11 表的完整迁移脚本）
  - BackupService（SQLite Online Backup + manifest）+ IntegrityChecker
  - 结构化日志（JsonLogFormatter）+ 错误追踪（LocalErrorTracker）
  - 前端契约骨架：Shell Ports（File/Camera/Scanner/Audio/Notification）、
    API Client Problem Details、Feature 模块 README
  - 架构契约测试（domain 零框架依赖、_ds 后缀合规、模块完整性）
  - 运维文档（migration.md, backup-recovery.md）
- 未完成：
  - 企业 SSO（替代 LocalIdentityProvider）
  - 生产级 Worker（替代 InProcessTaskRunner）
  - PostgreSQL/NAS/S3/Qdrant Adapter（替代 SQLite/本地文件）
  - React/Tauri 完整 UI（替代 Streamlit）
- 验证命令：
  - `uv run python -m pytest -q`
  - `uv run python -m ruff check .`
  - `uv run python -m mypy app config`
- 验证结果：`94 passed`；Ruff 全部通过；mypy 检查 107 个源文件无问题；Streamlit 七个 UI 标签页加载无异常
- 最新提交：`4c62e75`
- 已知问题：企业真实样张和现场指标仍需独立验收
- 下一位操作：提供验收输入后在真实环境下运行准确率脚本和性能基线
## Modular industrial architecture refactor (local branch only)

- Status: tasks 1–7 complete; task 8 (migrations, backup and integrity) is next.
- Working branch: `modular-architecture` in `.worktrees/modular-architecture`.
- Remote policy: local commits only. Do not push or deploy before the architecture acceptance task.
- Completed commits:
  - `b845e1b` — module entry points, settings, SQLite WAL/foreign-key/busy-timeout configuration.
  - `5e42263` — local identity provider and explicit role/permission policy.
  - `897e537` — UnitOfWork plus transactional review facade; audit failure rolls back versions.
  - `67ec488` — review leases, heartbeat/expiry, forced release reason, concurrency conflict and lease audit events.
  - `d495015` — persistent SQLite tasks, task-event sequencing, idempotency, retry, recovery and bounded in-process execution.
  - `c6a8bdb` — FastAPI app factory, request correlation, Problem Details, health and local identity endpoints.
  - `b289510` — versioned review leases, confirmation conflicts, task creation and resumable SSE events.
- Last verification: `76 passed`; `ruff check .` and `mypy app config` passed.
- Handoff: implement Task 8 from `docs/superpowers/plans/2026-07-12-modular-industrial-architecture-implementation.md`, then update verification results.
