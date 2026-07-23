import { useState } from "react";

import { uploadReportTemplate } from "./api";
import type { ReportTemplateVersion } from "./types";
import "./report-template-pages.css";

export function AdminReportTemplatesPage() {
  const [item, setItem] = useState<ReportTemplateVersion | null>(null);
  const [error, setError] = useState("");
  async function upload(file: File | undefined) {
    if (!file) return;
    try {
      setItem(await uploadReportTemplate(file));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "模板上传失败");
    }
  }
  return (
    <section className="report-template-page">
      <header><h1>外部报表模板</h1><p>仅接收 XLS/XLSX；上传后执行签名、宏、外链、公式和压缩风险检查。</p></header>
      {error && <div role="alert">{error}</div>}
      <label className="report-upload">
        选择工资表模板
        <input aria-label="选择工资表模板" type="file" accept=".xls,.xlsx" onChange={(event) => void upload(event.target.files?.[0])} />
      </label>
      {item && (
        <article>
          <strong>{item.filename}</strong>
          <span>{item.format} · {item.status}</span>
          <span>结构哈希：{item.structure_hash}</span>
          <span>{item.structure.sheets.length} 个工作表</span>
        </article>
      )}
    </section>
  );
}
