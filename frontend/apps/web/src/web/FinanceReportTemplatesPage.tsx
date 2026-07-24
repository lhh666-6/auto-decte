import { useEffect, useState } from "react";

import {
  confirmReportMapping,
  createReportMapping,
  listReportMappings,
  listReportTemplates,
} from "./api";
import type { ReportMappingVersion, ReportTemplateVersion } from "./types";
import { StatusBadge, PageHeader, EmptyState, ErrorAlert, SummaryCardGrid } from "./shared";
import type { SummaryCard } from "./shared";
import "./finance-pages.css";

function formatTime(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-CN");
  } catch {
    return iso;
  }
}

export function FinanceReportTemplatesPage() {
  const [templates, setTemplates] = useState<ReportTemplateVersion[]>([]);
  const [mappings, setMappings] = useState<ReportMappingVersion[]>([]);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");
  const [selectedTemplate, setSelectedTemplate] = useState<ReportTemplateVersion | null>(null);
  const [selectedMapping, setSelectedMapping] = useState<ReportMappingVersion | null>(null);
  const [showSample, setShowSample] = useState(false);

  function reload() {
    setError("");
    void Promise.all([listReportTemplates(), listReportMappings()])
      .then(([a, b]) => {
        setTemplates(a.items);
        setMappings(b.items);
        setLastUpdated(new Date().toLocaleString("zh-CN"));
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "模板数据加载失败");
      });
  }
  useEffect(reload, []);

  async function create(template: ReportTemplateVersion) {
    const sheet = template.structure.sheets[0]?.name;
    if (!sheet) return;
    try {
      const mapping = await createReportMapping(template.template_version_id, {
        sheet,
        start_row: 2,
        columns: [
          { column: 1, source_field: "subject_employee_code" },
          { column: 2, source_field: "business_date" },
        ],
      });
      setMappings((current) => [mapping, ...current]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "创建映射失败");
    }
  }

  async function confirm(item: ReportMappingVersion) {
    try {
      const updated = await confirmReportMapping(item.mapping_version_id);
      setMappings((current) =>
        current.map((value) =>
          value.mapping_version_id === updated.mapping_version_id ? updated : value,
        ),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "确认映射失败");
    }
  }

  function getMappingForTemplate(templateId: string): ReportMappingVersion[] {
    return mappings.filter((m) => m.template_version_id === templateId);
  }

  const overviewCards: SummaryCard[] = [
    { key: "templates", label: "模板数量", value: templates.length },
    { key: "mappings", label: "映射数量", value: mappings.length },
    { key: "confirmed", label: "已确认映射", value: mappings.filter((m) => m.status === "CONFIRMED").length },
  ];

  return (
    <section className="report-template-page" data-testid="finance-report-templates-page">
      <PageHeader title="报表模板与映射" subtitle="映射独立版本化；模板结构变化不会静默复用旧映射。" />

      {error && <ErrorAlert message={error} onRetry={reload} />}

      <div className="finance-ledger-meta">
        <span>模板数量：{templates.length}</span>
        <span>映射数量：{mappings.length}</span>
        <span>最后更新：{lastUpdated || "—"}</span>
      </div>

      <SummaryCardGrid cards={overviewCards} />

      {/* Templates table */}
      <h2>已分析模板</h2>
      {templates.length === 0 ? (
        <EmptyState message="暂无模板，请通过管理端上传。" />
      ) : (
        <div style={{ overflowX: "auto" }}>
          <table className="report-template-table">
            <thead>
              <tr>
                <th>模板名称</th>
                <th>版本</th>
                <th>状态</th>
                <th>工作表数</th>
                <th>数据来源</th>
                <th>映射版本</th>
                <th>最近样例</th>
                <th>审批状态</th>
                <th>启用范围</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {templates.map((item) => {
                const tmMappings = getMappingForTemplate(item.template_version_id);
                return (
                  <tr key={item.template_version_id}>
                    <td className="name-cell">{item.filename}</td>
                    <td>V1</td>
                    <td>
                      <StatusBadge status={item.status} />
                    </td>
                    <td>{item.structure.sheets.length}</td>
                    <td style={{ fontSize: 12, color: "#596579" }}>{item.format}</td>
                    <td style={{ fontSize: 12 }}>
                      {tmMappings.length > 0
                        ? tmMappings.map((m) => `V${m.version}`).join("、")
                        : "—"}
                    </td>
                    <td style={{ fontSize: 12, color: "#596579" }}>
                      {item.status === "ACTIVE" || item.status === "CONFIRMED" ? formatTime(new Date().toISOString()) : "—"}
                    </td>
                    <td>
                      {item.status === "PENDING_APPROVAL" ? (
                        <span style={{ color: "#8a6300", fontSize: 12 }}>待审批</span>
                      ) : item.status === "APPROVED" || item.status === "CONFIRMED" || item.status === "ACTIVE" ? (
                        <span style={{ color: "#1a6b3c", fontSize: 12 }}>已批准</span>
                      ) : (
                        <span style={{ color: "#8593a8", fontSize: 12 }}>—</span>
                      )}
                    </td>
                    <td style={{ fontSize: 12, color: "#596579" }}>
                      {item.status === "ACTIVE" ? "全部工厂" : "—"}
                    </td>
                    <td className="report-template-actions">
                      <button type="button" onClick={() => { setSelectedTemplate(item); setShowSample(true); }}>
                        样例预览
                      </button>
                      <button type="button" onClick={() => void create(item)}>
                        创建映射
                      </button>
                      {tmMappings.length > 0 && (
                        <button
                          type="button"
                          onClick={() => setSelectedMapping(tmMappings[0])}
                        >
                          查看映射
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Sample preview drawer */}
      {showSample && selectedTemplate && (
        <div className="finance-drawer-overlay" onClick={() => { setShowSample(false); setSelectedTemplate(null); }}>
          <div className="finance-drawer-content" onClick={(e) => e.stopPropagation()}>
            <div className="finance-drawer-header">
              <h2>{selectedTemplate.filename} — 样例预览</h2>
              <button className="finance-drawer-close" onClick={() => { setShowSample(false); setSelectedTemplate(null); }}>
                x
              </button>
            </div>
            <div className="finance-drawer-body">
              <div className="sample-preview-card" style={{ marginBottom: 16 }}>
                <div className="sample-preview-header">
                  <strong>{selectedTemplate.filename}</strong>
                  <button
                    type="button"
                    className="sample-preview-download"
                    onClick={() => {
                      window.open(`/api/v1/finance/report-templates/${selectedTemplate.template_version_id}/sample`, "_blank");
                    }}
                  >
                    下载样例
                  </button>
                </div>
                <div style={{ fontSize: 13, color: "#596579" }}>
                  <p>格式: {selectedTemplate.format} · 文件大小: {(selectedTemplate.size_bytes / 1024).toFixed(1)} KB</p>
                  <p>内容哈希: {selectedTemplate.file_hash?.slice(0, 16)}...</p>
                  <p>结构哈希: {selectedTemplate.structure_hash?.slice(0, 16)}...</p>
                </div>
                <div className="sample-preview-compare">
                  <span className="active">当前模板</span>
                  <span>对比旧模板</span>
                </div>
              </div>

              {/* Sheet structure */}
              <div className="finance-detail-section">
                <h3>工作表结构 ({selectedTemplate.structure.sheets.length})</h3>
                {selectedTemplate.structure.sheets.map((sheet, i) => (
                  <div key={i} style={{ padding: "8px 10px", background: "#f8fafc", borderRadius: 6, border: "1px solid #e7ecf2", fontSize: 13 }}>
                    <strong>{sheet.name}</strong> — 行数: {sheet.max_row} · 列数: {sheet.max_column}
                  </div>
                ))}
              </div>

              {selectedTemplate.warnings.length > 0 && (
                <div style={{ marginTop: 16 }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: 13, color: "#e07b16" }}>解析警告</h4>
                  <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12, color: "#596579" }}>
                    {selectedTemplate.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Mapping panel drawer */}
      {selectedMapping && (
        <div className="finance-drawer-overlay" onClick={() => setSelectedMapping(null)}>
          <div className="finance-drawer-content" onClick={(e) => e.stopPropagation()}>
            <div className="finance-drawer-header">
              <h2>映射 V{selectedMapping.version}</h2>
              <button className="finance-drawer-close" onClick={() => setSelectedMapping(null)}>
                x
              </button>
            </div>
            <div className="finance-drawer-body">
              <div className="finance-detail-section">
                <h3>基本信息</h3>
                <dl className="finance-detail-kv">
                  <dt>映射版本ID</dt><dd style={{ fontFamily: "monospace", fontSize: 12 }}>{selectedMapping.mapping_version_id}</dd>
                  <dt>模板版本ID</dt><dd style={{ fontFamily: "monospace", fontSize: 12 }}>{selectedMapping.template_version_id}</dd>
                  <dt>版本号</dt><dd>V{selectedMapping.version}</dd>
                  <dt>状态</dt><dd><StatusBadge status={selectedMapping.status} /></dd>
                  <dt>目标工作表</dt><dd>{selectedMapping.mapping_json.sheet}</dd>
                  <dt>起始行</dt><dd>{selectedMapping.mapping_json.start_row}</dd>
                </dl>
              </div>

              <div className="finance-detail-section" style={{ marginTop: 16 }}>
                <h3>字段映射 ({selectedMapping.mapping_json.columns.length} 列)</h3>
                {selectedMapping.mapping_json.columns.length === 0 ? (
                  <p style={{ color: "#596579", fontSize: 13 }}>暂无映射列</p>
                ) : (
                  <table className="mapping-table">
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>来源领域</th>
                        <th>来源字段</th>
                        <th>输出工作表</th>
                        <th>输出列</th>
                        <th>格式</th>
                        <th>必填</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedMapping.mapping_json.columns.map((col, i) => (
                        <tr key={i}>
                          <td>{i + 1}</td>
                          <td style={{ fontSize: 12 }}>
                            {col.source_field.startsWith("subject_") ? "提交事实" : col.source_field.startsWith("business_") ? "业务数据" : "系统字段"}
                          </td>
                          <td style={{ fontFamily: "monospace", fontSize: 12 }}>{col.source_field}</td>
                          <td>{selectedMapping.mapping_json.sheet}</td>
                          <td>列 {col.column}</td>
                          <td style={{ fontSize: 12, color: "#596579" }}>
                            {col.source_field.includes("date") ? "日期" : col.source_field.includes("amount") ? "金额" : "文本"}
                          </td>
                          <td className="required-mark">{col.source_field.includes("employee") || col.source_field.includes("code") ? "是" : "否"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div style={{ marginTop: 16, display: "flex", gap: 8 }}>
                {selectedMapping.status === "DRAFT" && (
                  <button
                    type="button"
                    onClick={() => void confirm(selectedMapping)}
                    style={{ padding: "8px 16px", border: 0, borderRadius: 6, color: "#fff", background: "#155eef", font: "inherit", fontSize: 13, fontWeight: 650, cursor: "pointer" }}
                  >
                    财务确认映射
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setSelectedMapping(null)}
                  style={{ padding: "8px 16px", border: "1px solid #b9c6d5", borderRadius: 6, background: "#fff", font: "inherit", fontSize: 13, cursor: "pointer" }}
                >
                  关闭
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Mappings list */}
      <h2>映射版本</h2>
      <div className="report-card-list">
        {mappings.length === 0 ? (
          <EmptyState message="暂无映射版本。" />
        ) : (
          mappings.map((item) => (
            <article key={item.mapping_version_id} onClick={() => setSelectedMapping(item)}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong>映射 V{item.version}</strong>
                <StatusBadge status={item.status} />
              </div>
              <span>
                工作表: {item.mapping_json.sheet} · {item.mapping_json.columns.length} 列映射 · 起始行: {item.mapping_json.start_row}
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                {item.status === "DRAFT" && (
                  <button
                    type="button"
                    onClick={(e) => { e.stopPropagation(); void confirm(item); }}
                    style={{ padding: "4px 12px", border: 0, borderRadius: 4, color: "#fff", background: "#155eef", font: "inherit", fontSize: 12, fontWeight: 650, cursor: "pointer" }}
                  >
                    财务确认映射
                  </button>
                )}
              </div>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
