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
- 已知问题：GitHub `origin` 尚未配置，本机也未验证仓库认证
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
- 已知问题：GitHub HTTPS 推送被本机 Schannel 证书错误 `0x80096004` 阻断
- 下一位操作：从本分支提交继续 P2；证书恢复后推送 `phase-0-bootstrap` 和 `phase-1-manual-loop`

## P2 查询与导出

- 状态：未开始
- 负责人：开发者 A

## P3 图像与识别

- 状态：未开始
- 负责人：开发者 B

## P4 规则与审计

- 状态：未开始
- 负责人：开发者 A 主导、开发者 B 审查

## P5 AI 与向量

- 状态：未开始
- 负责人：开发者 B 主导、开发者 A 审查

## P6 联调验收

- 状态：未开始
- 负责人：两位开发者共同完成
