import { useEffect, useState } from "react";

import {
  createGovernedExport,
  listGovernedExports,
  listReportMappings,
  previewGovernedExport,
  reexportGovernedExport,
} from "./api";
import type { ExportPreview } from "./api";
import type { GovernedExportBatch, ReportMappingVersion } from "./types";
import { StatusBadge, PageHeader, EmptyState, ErrorAlert, SummaryCardGrid } from "./shared";
import type { SummaryCard } from "./shared";
import "./finance-pages.css";

type TabKey = "create" | "history" | "reexport";
type CreateStep = 1 | 2 | 3;
type PreviewState = "idle" | "loading" | "result" | "stale";

function formatTime(iso: string): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("zh-CN");
  } catch {
    return iso;
  }
}

export function FinanceGovernedExportsPage() {
  const [mappings, setMappings] = useState<ReportMappingVersion[]>([]);
  const [batches, setBatches] = useState<GovernedExportBatch[]>([]);
  const [error, setError] = useState("");
  const [lastUpdated, setLastUpdated] = useState("");
  const [activeTab, setActiveTab] = useState<TabKey>("create");

  // Create export state
  const [createStep, setCreateStep] = useState<CreateStep>(1);
  const [selectedMapping, setSelectedMapping] = useState<ReportMappingVersion | null>(null);
  const [dateRange, setDateRange] = useState({ start: "", end: "" });
  const [selectedFactory, setSelectedFactory] = useState("");

  // Re-export state
  const [reExportBatch, setReExportBatch] = useState<GovernedExportBatch | null>(null);
  const [reExportStep, setReExportStep] = useState<"review" | "confirm">("review");

  // Preview state
  const [previewState, setPreviewState] = useState<PreviewState>("idle");
  const [previewData, setPreviewData] = useState<ExportPreview | null>(null);

  function reload() {
    setError("");
    void Promise.all([listReportMappings(), listGovernedExports()])
      .then(([a, b]) => {
        setMappings(a.items.filter((item) => item.status === "CONFIRMED"));
        setBatches(b.items);
        setLastUpdated(new Date().toLocaleString("zh-CN"));
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "导出数据加载失败");
      });
  }
  useEffect(reload, []);

  async function createExport() {
    if (!selectedMapping) return;
    try {
      const batch = await createGovernedExport(
        selectedMapping.template_version_id,
        selectedMapping.mapping_version_id,
        selectedFactory,
      );
      setBatches((current) => [batch, ...current]);
      setCreateStep(1);
      setSelectedMapping(null);
      setDateRange({ start: "", end: "" });
      setSelectedFactory("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "创建导出失败");
    }
  }

  async function handleReExport() {
    if (!reExportBatch) return;
    try {
      const batch = await reexportGovernedExport(
        reExportBatch.export_batch_id,
        reExportBatch.template_version_id,
        reExportBatch.mapping_version_id,
        "",
      );
      setBatches((current) => [batch, ...current]);
      setReExportBatch(null);
      setReExportStep("review");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "重导失败");
    }
  }

  async function handlePreview() {
    if (!selectedMapping) return;
    setPreviewState("loading");
    setPreviewData(null);
    setError("");
    try {
      const preview = await previewGovernedExport(
        selectedMapping.template_version_id,
        selectedMapping.mapping_version_id,
        selectedFactory,
      );
      setPreviewData(preview);
      setPreviewState("result");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "预览生成失败");
      setPreviewState("idle");
    }
  }

  // Mark preview stale when scope changes after a successful preview
  function markPreviewStale() {
    if (previewState === "result") {
      setPreviewState("stale");
    }
  }

  function needsReExport(batch: GovernedExportBatch): boolean {
    return batch.status === "FAILED" || batch.status === "EXPIRED" || batch.status === "SUPERSEDED";
  }

  const confirmedMappings = mappings;
  const reExportBatches = batches.filter(needsReExport);

  const overviewCards: SummaryCard[] = [
    { key: "available", label: "可用映射", value: confirmedMappings.length },
    { key: "batches", label: "导出批次", value: batches.length },
    { key: "needReexport", label: "需重导", value: reExportBatches.length },
  ];

  return (
    <section className="export-center-page" data-testid="finance-exports-page">
      <PageHeader title="正式报表导出" subtitle="导出冻结模板、映射、筛选和数据水位；只有重开校验通过的文件可下载。" />

      {error && <ErrorAlert message={error} onRetry={reload} />}

      <div className="finance-ledger-meta">
        <span>可用映射：{confirmedMappings.length}</span>
        <span>导出批次：{batches.length}</span>
        <span>最后更新：{lastUpdated || "—"}</span>
      </div>

      <SummaryCardGrid cards={overviewCards} />

      {/* Tabs */}
      <nav className="export-tabs" data-testid="finance-export-tabs">
        {([
          ["create", "创建导出"],
          ["history", "导出历史"],
          ["reexport", "需重导"],
        ] as [TabKey, string][]).map(([key, label]) => (
          <button
            key={key}
            type="button"
            className={`export-tab ${activeTab === key ? "export-tab--active" : ""}`}
            onClick={() => setActiveTab(key)}
          >
            {label}
            {key === "history" && (
              <span className="export-tab-count">{batches.length}</span>
            )}
            {key === "reexport" && (
              <span className="export-tab-count">{reExportBatches.length}</span>
            )}
          </button>
        ))}
      </nav>

      {/* Tab: Create Export */}
      {activeTab === "create" && (
        <div style={{ display: "grid", gap: 16 }}>
          {/* Step indicator */}
          <div className="export-create-steps">
            {([1, 2, 3] as CreateStep[]).map((step, idx) => (
              <span key={step} style={{ display: "flex", alignItems: "center", gap: 4 }}>
                <span
                  className={`export-step ${createStep === step ? "export-step--active" : createStep > step ? "export-step--done" : ""}`}
                >
                  <span className="export-step-num">{createStep > step ? "✓" : step}</span>
                  {step === 1 ? "选择范围" : step === 2 ? "预览确认" : "创建导出"}
                </span>
                {idx < 2 && <span className="export-step-divider" />}
              </span>
            ))}
          </div>

          {/* Step 1: Select scope */}
          {createStep === 1 && (
            <div className="export-step-form">
              <h3 style={{ margin: 0, fontSize: 14 }}>选择导出范围</h3>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
                <label>
                  开始日期
                  <input
                    type="date"
                    value={dateRange.start}
                    onChange={(e) => setDateRange((d) => ({ ...d, start: e.target.value }))}
                  />
                </label>
                <label>
                  结束日期
                  <input
                    type="date"
                    value={dateRange.end}
                    onChange={(e) => setDateRange((d) => ({ ...d, end: e.target.value }))}
                  />
                </label>
              </div>
              <label>
                目标工厂
                <input
                  value={selectedFactory}
                  onChange={(e) => setSelectedFactory(e.target.value)}
                  placeholder="留空表示所有工厂"
                />
              </label>
              <label>
                数据来源
                <input value="正式提交与已确认更正" disabled style={{ background: "#f8fafc" }} />
              </label>
              <label>
                正式批次编号
                <input placeholder="留空使用当前最新" />
              </label>
              <label>
                报表模板
                <select
                  value={selectedMapping?.mapping_version_id ?? ""}
                  onChange={(e) => {
                    const m = confirmedMappings.find((x) => x.mapping_version_id === e.target.value);
                    setSelectedMapping(m ?? null);
                  }}
                >
                  <option value="">-- 选择映射版本 --</option>
                  {confirmedMappings.map((m) => (
                    <option key={m.mapping_version_id} value={m.mapping_version_id}>
                      映射 V{m.version} ({m.mapping_json.sheet})
                    </option>
                  ))}
                </select>
              </label>
              <div className="export-step-actions">
                <button type="button" className="primary" onClick={() => { setPreviewState("idle"); setPreviewData(null); setCreateStep(2); }} disabled={!selectedMapping}>
                  下一步：预览
                </button>
              </div>
            </div>
          )}

          {/* Step 2: Read-only preview */}
          {createStep === 2 && selectedMapping && (
            <div style={{ display: "grid", gap: 14 }}>
              <h3 style={{ margin: 0, fontSize: 14 }}>导出预览（只读）</h3>
              <div className="export-preview-kv">
                <dt>模板版本</dt>
                <dd style={{ fontFamily: "monospace", fontSize: 12 }}>{selectedMapping.template_version_id}</dd>
                <dt>映射版本</dt>
                <dd>V{selectedMapping.version} (ID: {selectedMapping.mapping_version_id.slice(0, 12)}...)</dd>
                <dt>日期范围</dt>
                <dd>{dateRange.start || "不限"} 至 {dateRange.end || "不限"}</dd>
                <dt>目标工厂</dt>
                <dd>{selectedFactory || "全部"}</dd>
                <dt>正式记录数</dt>
                <dd style={{ fontWeight: 650 }}>
                  {previewState === "result" || previewState === "stale"
                    ? `${previewData?.record_count ?? "—"} 条`
                    : previewState === "loading"
                      ? "加载中…"
                      : "—"}
                  {previewState === "stale" && (
                    <span style={{ color: "#e07b16", fontSize: 11, marginLeft: 6 }}>（范围已变更）</span>
                  )}
                </dd>
                <dt>涉及员工数</dt>
                <dd style={{ fontWeight: 650 }}>
                  {previewState === "result" || previewState === "stale"
                    ? `${previewData?.employee_count ?? "—"} 人`
                    : "—"}
                </dd>
                <dt>总金额</dt>
                <dd style={{ fontWeight: 650, fontVariantNumeric: "tabular-nums" }}>
                  {previewState === "result" || previewState === "stale"
                    ? `¥ ${previewData?.total_amount ?? "—"}`
                    : "—"}
                </dd>
                <dt>异常数</dt>
                <dd style={{ color: "#e07b16" }}>
                  {previewState === "result" || previewState === "stale"
                    ? `${previewData?.anomaly_count ?? "—"} 条`
                    : "—"}
                </dd>
                <dt>需重导来源数</dt>
                <dd style={{ color: "#9d2424" }}>—</dd>
              </div>
              {previewState === "idle" && (
                <div className="export-step-actions">
                  <button type="button" className="secondary" onClick={() => setCreateStep(1)}>
                    返回修改
                  </button>
                  <button type="button" className="primary" onClick={() => void handlePreview()}>
                    请先生成预览
                  </button>
                </div>
              )}
              {previewState === "loading" && (
                <div className="export-step-actions">
                  <button type="button" className="secondary" onClick={() => setCreateStep(1)}>
                    返回修改
                  </button>
                  <button type="button" className="primary" disabled>
                    预览生成中…
                  </button>
                </div>
              )}
              {(previewState === "result" || previewState === "stale") && (
                <div className="export-step-actions">
                  <button type="button" className="secondary" onClick={() => { setCreateStep(1); markPreviewStale(); }}>
                    返回修改
                  </button>
                  <button
                    type="button"
                    className="primary"
                    onClick={() => void handlePreview()}
                    style={previewState === "stale" ? { background: "#e07b16" } : undefined}
                  >
                    {previewState === "stale" ? "重新生成预览" : "刷新预览"}
                  </button>
                  <button
                    type="button"
                    className="primary"
                    onClick={() => setCreateStep(3)}
                    disabled={previewState === "stale"}
                  >
                    下一步：确认创建
                  </button>
                </div>
              )}
              {previewState === "stale" && (
                <p style={{ margin: 0, fontSize: 12, color: "#e07b16" }}>
                  范围已变更，预览数据可能不准确。请重新生成预览后再创建。
                </p>
              )}
            </div>
          )}

          {/* Step 3: Confirm creation */}
          {createStep === 3 && selectedMapping && (
            <div style={{ display: "grid", gap: 14 }}>
              <h3 style={{ margin: 0, fontSize: 14 }}>确认创建导出</h3>
              <div style={{ background: "#f8fafc", border: "1px solid #e7ecf2", borderRadius: 8, padding: 14, fontSize: 13, color: "#596579" }}>
                <p style={{ margin: "0 0 6px" }}>
                  创建后系统将：
                </p>
                <ul style={{ margin: 0, paddingLeft: 18 }}>
                  <li>冻结当前模板版本、映射版本和数据水位</li>
                  <li>生成分工作表 Excel 文件</li>
                  <li>计算文件哈希并记录日志</li>
                  <li>导出完成后可下载，失败不产生半成品</li>
                </ul>
              </div>
              <div style={{ fontSize: 13, color: "#596579" }}>
                幂等键: <code style={{ background: "#f0f3f7", padding: "2px 6px", borderRadius: 4, fontSize: 11 }}>{crypto.randomUUID()}</code>
              </div>
              <div className="export-step-actions">
                <button type="button" className="secondary" onClick={() => setCreateStep(2)}>
                  返回预览
                </button>
                <button type="button" className="primary" onClick={() => void createExport()}>
                  确认创建并生成文件
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tab: Export History */}
      {activeTab === "history" && (
        <div>
          {batches.length === 0 ? (
            <EmptyState message="暂无导出批次。" />
          ) : (
            <div style={{ overflowX: "auto" }}>
              <table className="export-history-table">
                <thead>
                  <tr>
                    <th>导出批次</th>
                    <th>创建时间</th>
                    <th>创建人</th>
                    <th>模板版本</th>
                    <th>映射版本</th>
                    <th>数据范围</th>
                    <th>记录数</th>
                    <th>文件哈希</th>
                    <th>状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map((item) => (
                    <tr key={item.export_batch_id}>
                      <td style={{ fontFamily: "monospace", fontSize: 12, maxWidth: 140, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={item.export_batch_id}>
                        {item.download_name || item.export_batch_id.slice(0, 12)}
                      </td>
                      <td style={{ fontSize: 12 }}>{formatTime(new Date().toISOString())}</td>
                      <td style={{ fontSize: 12 }}>财务</td>
                      <td style={{ fontFamily: "monospace", fontSize: 11 }}>
                        {item.template_version_id?.slice(0, 10)}...
                      </td>
                      <td style={{ fontSize: 12 }}>
                        {item.mapping_version_id?.slice(0, 10)}...
                      </td>
                      <td style={{ fontSize: 12, color: "#596579" }}>
                        {item.data_watermark ? "水位: " + item.data_watermark : "—"}
                      </td>
                      <td style={{ fontSize: 12 }}>—</td>
                      <td style={{ fontFamily: "monospace", fontSize: 11 }}>
                        {item.file_hash ? item.file_hash.slice(0, 14) + "..." : "—"}
                      </td>
                      <td>
                        <StatusBadge status={item.status} />
                      </td>
                      <td className="export-history-actions">
                        {item.status === "AVAILABLE" && (
                          <a href={`/api/v1/finance/exports/${item.export_batch_id}/download`} style={{ color: "#155eef" }}>
                            下载
                          </a>
                        )}
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedMapping(confirmedMappings[0] ?? null);
                          }}
                        >
                          详情
                        </button>
                        <a href={`/api/v1/finance/exports/${item.export_batch_id}/lineage`}>
                          血缘
                        </a>
                        {needsReExport(item) && (
                          <button
                            type="button"
                            onClick={() => { setReExportBatch(item); setActiveTab("reexport"); }}
                            style={{ color: "#155eef", fontWeight: 650 }}
                          >
                            重导
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Tab: Needs Re-export */}
      {activeTab === "reexport" && (
        <div>
          {reExportBatches.length === 0 ? (
            <EmptyState message="没有需要重新导出的批次。" />
          ) : reExportBatch ? (
            <div style={{ display: "grid", gap: 14 }}>
              {reExportStep === "review" && (
                <>
                  <div className="reexport-compare">
                    {/* Original export info */}
                    <div className="reexport-card">
                      <h4>原导出</h4>
                      <div style={{ fontSize: 13 }}>
                        <p style={{ margin: "0 0 4px" }}>
                          批次: <code style={{ fontSize: 11 }}>{reExportBatch.export_batch_id.slice(0, 16)}...</code>
                        </p>
                        <p style={{ margin: "0 0 4px" }}>
                          状态: <StatusBadge status={reExportBatch.status} />
                        </p>
                        <p style={{ margin: 0 }}>
                          模板版本: {reExportBatch.template_version_id?.slice(0, 12)}...
                        </p>
                      </div>
                    </div>
                    {/* New export preview */}
                    <div className="reexport-card">
                      <h4>新导出预览</h4>
                      <div style={{ fontSize: 13 }}>
                        <p style={{ margin: "0 0 4px" }}>
                          映射版本: {reExportBatch.mapping_version_id?.slice(0, 12)}...
                        </p>
                        <p style={{ margin: "0 0 4px" }}>
                          数据水位: 将使用最新有效数据
                        </p>
                        <p style={{ margin: 0, color: "#155eef" }}>
                          模板和映射不变，仅更新数据。
                        </p>
                      </div>
                    </div>
                  </div>
                  <div className="reexport-card">
                    <h4>重导原因</h4>
                    <div className="reason-text">
                      {reExportBatch.status === "FAILED"
                        ? "原批次生成失败，需重新创建"
                        : reExportBatch.status === "EXPIRED"
                          ? "原批次已过期，数据水位已更新"
                          : "原批次已被新批次替代"}
                    </div>
                  </div>
                  <div className="export-step-actions">
                    <button type="button" className="secondary" onClick={() => { setReExportBatch(null); setReExportStep("review"); }}>
                      取消
                    </button>
                    <button type="button" className="primary" onClick={() => setReExportStep("confirm")}>
                      预览新导出
                    </button>
                  </div>
                </>
              )}

              {reExportStep === "confirm" && (
                <div style={{ display: "grid", gap: 14 }}>
                  <h3 style={{ margin: 0, fontSize: 14 }}>确认重导</h3>
                  <div style={{ background: "#f8fafc", border: "1px solid #e7ecf2", borderRadius: 8, padding: 14, fontSize: 13, color: "#596579" }}>
                    <p style={{ margin: "0 0 6px" }}>
                      重导将使用原始导出相同的模板版本和映射版本，但使用最新的数据水位。原导出批次会保留在历史记录中。
                    </p>
                    <p style={{ margin: 0 }}>
                      新导出幂等键: <code style={{ background: "#f0f3f7", padding: "2px 6px", borderRadius: 4, fontSize: 11 }}>{crypto.randomUUID()}</code>
                    </p>
                  </div>
                  <div className="export-step-actions">
                    <button type="button" className="secondary" onClick={() => setReExportStep("review")}>
                      返回
                    </button>
                    <button type="button" className="primary" onClick={() => void handleReExport()}>
                      确认重导
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="report-card-list">
              {reExportBatches.map((item) => (
                <article key={item.export_batch_id} onClick={() => setReExportBatch(item)}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <strong style={{ fontFamily: "monospace", fontSize: 13 }}>
                      {item.download_name || item.export_batch_id.slice(0, 16)}
                    </strong>
                    <StatusBadge status={item.status} />
                  </div>
                  <span>
                    水位 {item.data_watermark} · {item.file_hash ? `校验: ${item.file_hash.slice(0, 12)}...` : "未校验"}
                  </span>
                  <div style={{ display: "flex", gap: 8 }}>
                    <span style={{ color: "#9d2424", fontSize: 12 }}>
                      {item.status === "FAILED" ? "生成失败" : item.status === "EXPIRED" ? "已过期" : "已被替代"}
                    </span>
                    <button
                      type="button"
                      onClick={(e) => { e.stopPropagation(); setReExportBatch(item); }}
                      style={{ padding: "4px 12px", border: "1px solid #155eef", borderRadius: 4, color: "#155eef", background: "#fff", font: "inherit", fontSize: 12, cursor: "pointer", fontWeight: 650 }}
                    >
                      重导
                    </button>
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
