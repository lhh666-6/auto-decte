# 工业级产量数据采集 Demo

面向 Windows 10/11 的单机产量表单采集系统。首个版本优先保证在 OCR、AI
和向量检索关闭时，仍能完成导入、人工复核、查询、追溯和 XLSX 导出。

## 协作者先读

当前集成分支是 `modular-architecture`，不要从本地 `main` 继续开发，也不要重复创建 `phase-*` 分支。拉取后先阅读：

- [跨账户 Codex 交接](docs/CODEX_HANDOFF.md)
- [明文进度记录](PROGRESS.md)
- [模板中心实施计划](docs/superpowers/plans/2026-07-13-template-center-studio-implementation.md)

当前模板中心计划 Task 1–5 已完成；下一任务是 Task 6“可视化画布编辑器与字段属性检查器”。四个企业通用模板已经完成分类和字段映射，但尚未作为幂等安装数据真正落库。

```powershell
git fetch origin
git switch modular-architecture
git pull --ff-only origin modular-architecture
git status --short
```

开始修改前，`git status --short` 应无输出。除非项目负责人明确要求，不要创建新分支、修改 `main`、删除历史分支或重新实现已完成的 Task 1–5。

## 开发环境

```powershell
uv sync --extra dev
uv run python -m pytest -v
uv run python -m ruff check .
uv run streamlit run app/ui/main.py
```

React 审核工作台（Web Shell）可与 API 同时运行：

```powershell
uv run python -m uvicorn app.api.main:create_app --factory --host 127.0.0.1 --port 8000
cd frontend
npm install
npm run dev:web
```

浏览器打开 Vite 启动日志显示的地址（默认从 `5173` 开始，端口占用时会自动递增；本机最近使用 `http://127.0.0.1:5175/`）。Web 开发服务器会将 `/api` 代理到本地 8000 端口；生产身份认证完成前，不要在浏览器请求中传递 `X-Roles`。

复制 `.env.example` 为 `.env` 后可修改本地数据目录。不要将真实表单、员工数据、
录音、数据库、导出文件或密钥提交到 GitHub。

协作状态和接力操作见 [PROGRESS.md](PROGRESS.md)。模块化架构、React/Web + Tauri 目标界面、当前已验证能力和队友 Codex 的任务清单见 [docs/CODEX_HANDOFF.md](docs/CODEX_HANDOFF.md)。

## 当前功能

- 图片证据导入、SHA-256 去重和条件录音绑定
- 人工确认、更正、不可变版本和审计事件
- 图像质量、二维码分类、透视校正、数字候选和 OMR
- 确定性业务规则、精确查询和完整追溯
- 四工作表 XLSX 导出和导出后更正提醒
- 默认关闭的 AI 建议 Adapter 与本地相似异常检索
- React 左图右表审核工作台、受控图片导入和真实审核队列
- 模板 QR、ArUco 校正、标准画布、字段裁切和识别候选
- 模板库、发布版本只读预览、复制调优、草稿恢复、预检和发布

尚未完成：可拖动/缩放的模板画布、四个通用模板的安装 seed、审核草稿/退回/作废/确认并下一张、主数据 CRUD、产品化导出中心、模板包/纸张实例闭环和 Tauri 桌面壳。完整边界以交接文档为准。

OCR、OMR 和 AI 输出均为候选，不会覆盖人工确认事实。AI 关闭时核心流程仍可运行。

## 本地运行与恢复

运行数据默认位于 `data/`：SQLite 数据库、证据、导出文件需要一起备份。恢复时先关闭
应用，将完整备份恢复到同一数据根目录，再启动应用并通过追溯页抽查表单、证据和导出批次。
原始证据不得覆盖；重新采集必须生成新的证据记录。

## GitHub 接力

```powershell
git fetch origin
git switch modular-architecture
git pull --ff-only origin modular-architecture
git status --short
uv sync --extra dev
```

协作者 Codex 完成分配任务后，应先运行与修改范围相称的定向测试，再更新 `PROGRESS.md`，写明验证命令、结果、提交号、已知问题和下一位操作，然后提交并推送 `modular-architecture`。不要自行创建新的长期分支；如确需独立分支，先与项目负责人确认。
真实业务数据、录音、数据库、导出文件和密钥不得提交。
