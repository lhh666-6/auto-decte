# Web 转型阶段 6：外部模板、映射与正式导出

## 已实现

- 管理员通过 Web 上传 `.xls` 或 `.xlsx` 外部模板。
- 上传执行扩展名、文件签名、大小、哈希、损坏、压缩炸弹、宏、外部链接、DDE/危险公式检查。
- XLS 和 XLSX 均解析工作表、使用区域、合并区域等统一结构；旧版 XLS 导出时转换为 XLSX。
- 模板内容和结构分别计算不可变 SHA-256。
- 财务创建并确认独立版本化字段映射；映射必须绑定精确模板版本。
- 未确认映射不能正式导出。
- 导出冻结筛选条件、模板版本、映射版本、数据水位、操作人和幂等键。
- 输出单元格防公式注入，并在保存后重新打开校验；只有通过校验的文件标记为 `AVAILABLE`。
- 导出文件和历史批次不覆盖；下载前再次校验内容哈希和工作簿可读性。
- 每个写入单元格保存工作表、行列、地址、来源提交和来源字段血缘。
- 已用项目真实的 `叉车工日工资计算表.xls` 完成 xlrd 解析烟测。

## 关键接口

- `POST /api/v1/admin/report-templates`
- `GET /api/v1/finance/report-templates`
- `POST /api/v1/finance/report-templates/{id}/analyze`
- `GET/POST /api/v1/finance/report-mappings`
- `POST /api/v1/finance/report-mappings/{id}/confirm`
- `GET/POST /api/v1/finance/exports`
- `GET /api/v1/finance/exports/{id}`
- `GET /api/v1/finance/exports/{id}/download`
- `GET /api/v1/finance/exports/{id}/lineage`

## 数据不变量

1. 模板哈希相同则复用同一版本。
2. 模板结构变化后旧映射不能绑定新模板。
3. 导出幂等键相同但请求不同则冲突。
4. 非 `AVAILABLE` 或哈希不匹配文件不可下载。
5. 每个导出单元格只能有一条确定来源血缘。
