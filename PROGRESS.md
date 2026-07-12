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
- 下一位操作：从本分支提交继续 P2；证书恢复后推送 `phase-0-bootstrap` 和 `phase-1-manual-loop`

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
- 下一位操作：从本分支继续 P4 规则与审计；P3 留给开发者 B

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
- 已知问题：P3 尚未由开发者 B 实现；远程阶段分支 `phase-4-rules-audit` 已保留
- 下一位操作：开发者 B 完成 P3 后，扩展审计完整性测试覆盖人工重分类和识别 Attempt

## P5 AI 与向量

- 状态：未开始
- 负责人：开发者 B 主导、开发者 A 审查

## P6 联调验收

- 状态：未开始
- 负责人：两位开发者共同完成
