# Web 转型阶段 7：旧识别链路退役

## 已退役运行入口

- 删除旧桌面一级导航和 `AppShell`。
- 删除 `/workbench/*`、`/templates/*`、`/master-data/*`、旧 `/exports` 的前端路由。
- FastAPI 不再注册旧图片导入、分类、识别审核、审核工作台、旧模板、旧任务和旧导出路由。
- 启动时不再恢复旧识别任务和旧导出任务。
- 移动端聚合路由、请求/响应 Schema 和 `frontend/apps/web/src/mobile/**` 保持冻结。

## 数据退役策略

迁移 `027` 不直接丢弃历史事实，而是：

1. 将旧识别运行表重命名到 `legacy_archive_*` 只读归档命名空间；
2. 在 `legacy_retirement_manifest` 保存每张表的行数和退役时间；
3. 原表名消失，运行代码无法继续写入旧链路；
4. 保留表单、字段、审计、事实记录、电子提交和全部移动端数据。

归档表包括：

- `recognition_attempts`
- `evidence_files`
- `ai_reviews`
- `review_leases`
- `review_drafts`
- `task_events`
- `tasks`
- `export_batches`

## 图片清理

使用：

```powershell
uv run --frozen python scripts/retire_legacy_recognition.py `
  --data-root D:\path\to\data `
  --output-dir D:\path\to\backups
```

默认只生成一致性数据库备份、证据清单、SHA-256 和清理报告，不删除文件。复核后增加 `--apply`：

- 先用 SQLite backup API 生成一致性快照；
- 将数据库、归档证据文件和清单写入 ZIP；
- 完整执行 ZIP CRC 校验；
- 只删除 `legacy_archive_evidence_files` 明确引用且位于指定 evidence 根目录内的文件；
- 不删除移动端现用文件或目录外文件。

生产数据库迁移和 `--apply` 必须在服务停止后执行；本次代码验收使用隔离数据库验证了完整备份—校验—删除顺序，没有直接修改正在运行的本地数据。

## 验收结果

- 旧桌面 API 注册：0
- 旧桌面路由与导航：0
- 退役归档表：8
- 新主线 + 移动端后端验收：90 项通过
- 前端全量：通过
- 移动端边界检查：通过
- 迁移后生产模式启动：通过

## 历史本地库接管

早期由 `create_all` 建立且没有 Alembic 版本号的数据库，会在启动时先完成兼容结构检查，安全标记为 `026`，再执行 `027` 归档。全新数据库直接执行完整 Alembic 迁移链。
