# 开发进度与接力记录

> 本文件是两位 Codex 协作时的唯一明文接力状态。每次功能提交必须同步更新。

## P0 项目初始化

- 状态：已完成
- 负责人：开发者 A（仓库所有者）
- 分支：`phase-0-bootstrap`
- 开始时间：2026-07-12
- 完成时间：2026-07-12
- 已完成：
  - 建立 Python 3.11 项目配置和开发依赖
  - 建立环境配置、Streamlit 入口和测试框架
  - 建立 Git 忽略规则和协作说明
- 未完成：
  - 写入最终提交哈希并推送 GitHub
- 验证命令：`python -m pytest -v`；`python -m ruff check .`
- 验证结果：`1 passed`；Ruff `All checks passed!`；mypy `Success: no issues found in 5 source files`
- 最新提交：`d8d2b6c`
- 已知问题：`origin` 已配置；HTTPS 返回错误代理证书，SSH 无可用公钥，GitHub App 也无法访问目标仓库
- 下一位操作：P0 合并后从最新 `main` 创建 `phase-1-manual-loop`

## P1 人工闭环

- 状态：已完成（本地，待 GitHub 推送）
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
- 未完成：GitHub 推送与 Pull Request
- 验证命令：
  - `uv run python -m pytest -q`
  - `uv run python -m ruff check .`
  - `uv run python -m mypy app config`
  - `uv run python -c "from streamlit.testing.v1 import AppTest; ..."`
- 验证结果：`14 passed`；Ruff 全部通过；mypy 检查 22 个源文件无问题；Streamlit 无异常并显示“批量导入/人工复核”
- 最新提交：`71e8001`
- 已知问题：GitHub HTTPS 返回非 GitHub 证书，SSH 无可用公钥，GitHub App 对目标仓库返回 Not Found
- 下一位操作：从本分支提交继续 P2；证书恢复后推送 `phase-0-bootstrap` 和 `phase-1-manual-loop`

## P2 查询与导出

- 状态：已完成（本地，待 GitHub 推送）
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
- 未完成：GitHub 推送与 Pull Request
- 验证命令：`uv run python -m pytest -q`；`uv run python -m ruff check .`；`uv run python -m mypy app config`；Streamlit AppTest
- 验证结果：`18 passed`；Ruff 全部通过；mypy 检查 28 个源文件无问题；四个 UI 标签页加载无异常
- 最新提交：`943a174`
- 已知问题：GitHub HTTPS 返回非 GitHub 证书，SSH 无可用公钥，GitHub App 对目标仓库返回 Not Found
- 下一位操作：从本分支继续 P4 规则与审计；P3 留给开发者 B

## P3 图像与识别

- 状态：未开始
- 负责人：开发者 B

## P4 规则与审计

- 状态：已完成开发者 A 部分（本地，待开发者 B 审查）
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
- 已知问题：P3 尚未由开发者 B 实现；三种安全 GitHub 通道均无法访问目标仓库
- 下一位操作：开发者 B 完成 P3 后，扩展审计完整性测试覆盖人工重分类和识别 Attempt

## P5 AI 与向量

- 状态：未开始
- 负责人：开发者 B 主导、开发者 A 审查

## P6 联调验收

- 状态：未开始
- 负责人：两位开发者共同完成
