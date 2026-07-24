import { useCallback, useEffect, useState } from "react";

import { uploadReportTemplate } from "./api";
import type { ReportTemplateVersion } from "./types";
import "./report-template-pages.css";
import "./workspace.css";

/* ------------------------------------------------------------------ */
/*  component                                                          */
/* ------------------------------------------------------------------ */

export function AdminReportTemplatesPage() {
  const [item, setItem] = useState<ReportTemplateVersion | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const upload = useCallback(async (file: File | undefined) => {
    if (!file) return;
    setLoading(true);
    setError("");
    try {
      const result = await uploadReportTemplate(file);
      setItem(result);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "模板上传失败");
    } finally {
      setLoading(false);
    }
  }, []);

  /* clear stale errors on unmount-equivalent */
  useEffect(() => {
    return () => { setError(""); };
  }, []);

  return (
    <section className="report-template-page">
      <header>
        <h1>外部报表模板</h1>
        <p>仅接收 XLS/XLSX；上传后执行签名、宏、外链、公式和压缩风险检查。</p>
      </header>

      {error && <div role="alert" className="error-banner">{error}</div>}

      <label className="report-upload">
        选择工资表模板
        <input
          aria-label="选择工资表模板"
          type="file"
          accept=".xls,.xlsx"
          disabled={loading}
          onChange={(event) => { void upload(event.target.files?.[0]); }}
        />
      </label>

      {loading && <div role="status" className="page-loading">正在上传并分析模板...</div>}

      {!loading && !item && !error && (
        <p className="vex-empty">尚未上传任何报表模板。请选择 XLS/XLSX 文件上传。</p>
      )}

      {item && !loading && (
        <article className="report-template-detail">
          <div className="report-template-header">
            <strong>{item.filename}</strong>
            <span className={`managed-status ${item.status === "APPROVED" ? "" : "vex-status-open"}`}>
              {item.status}
            </span>
          </div>

          <div className="report-template-meta">
            <span>格式：{item.format}</span>
            <span>大小：{(item.size_bytes / 1024).toFixed(1)} KB</span>
            <span>结构哈希：{item.structure_hash}</span>
            <span>{item.structure.sheets.length} 个工作表</span>
          </div>

          {/* sheet list */}
          {item.structure.sheets.length > 0 && (
            <div className="report-sheets">
              <h4>工作表清单</h4>
              <table className="diff-table">
                <thead>
                  <tr>
                    <th>工作表名称</th>
                    <th>最大行</th>
                    <th>最大列</th>
                  </tr>
                </thead>
                <tbody>
                  {item.structure.sheets.map((sheet) => (
                    <tr key={sheet.name}>
                      <td>{sheet.name}</td>
                      <td>{sheet.max_row}</td>
                      <td>{sheet.max_column}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* warnings */}
          {item.warnings.length > 0 && (
            <div className="report-warnings">
              <h4>风险警告</h4>
              <ul>
                {item.warnings.map((warning, i) => (
                  <li key={`warn-${i}`} className="precheck-warning-item">{warning}</li>
                ))}
              </ul>
            </div>
          )}
        </article>
      )}
    </section>
  );
}
