# 工业级产量数据采集 Demo

面向 Windows 10/11 的单机产量表单采集系统。首个版本优先保证在 OCR、AI
和向量检索关闭时，仍能完成导入、人工复核、查询、追溯和 XLSX 导出。

## 开发环境

```powershell
uv sync --extra dev
uv run python -m pytest -v
uv run python -m ruff check .
uv run streamlit run app/ui/main.py
```

复制 `.env.example` 为 `.env` 后可修改本地数据目录。不要将真实表单、员工数据、
录音、数据库、导出文件或密钥提交到 GitHub。

协作状态和接力操作见 [PROGRESS.md](PROGRESS.md)。
