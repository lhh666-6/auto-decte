import { useCallback, useEffect, useMemo, useState } from "react";

import { ErrorAlert, PageHeader } from "./shared/SummaryCardGrid";

interface PositionDataItem {
  record_id: string;
  display_no: string;
  form_type: string;
  factory_id: string;
  date: string;
  employee_code: string;
  employee_name: string;
  stage: string;
  cage_no: string;
  values: Record<string, unknown>;
  status: string;
  current_stage: string;
}

const STAGE_OPTIONS = [
  { value: "SORT", label: "分选工" },
  { value: "DIPPING", label: "浸胶工" },
  { value: "DRYING", label: "干燥工" },
];

const STAGE_LABELS: Record<string, string> = { SORT: "分选", DIPPING: "浸胶", DRYING: "干燥" };

export function FinancePositionDataPage() {
  const [items, setItems] = useState<PositionDataItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [factoryId, setFactoryId] = useState("");
  const [stage, setStage] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [exporting, setExporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const params = new URLSearchParams();
      if (factoryId) params.set("factory_id", factoryId);
      if (stage) params.set("stage", stage);
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (employeeSearch.trim()) params.set("employee_code", employeeSearch.trim());
      const resp = await fetch(`/api/v1/finance/position-data?${params.toString()}`, { credentials: "include" });
      if (!resp.ok) throw new Error(`请求失败 (${resp.status})`);
      const data = (await resp.json()) as { items: PositionDataItem[]; count: number };
      setItems(data.items ?? []);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "数据加载失败");
    } finally {
      setLoading(false);
    }
  }, [factoryId, stage, dateFrom, dateTo, employeeSearch]);

  useEffect(() => { void load(); }, [load]);

  async function handleExport() {
    setExporting(true);
    try {
      const params = new URLSearchParams();
      if (factoryId) params.set("factory_id", factoryId);
      if (stage) params.set("stage", stage);
      if (dateFrom) params.set("date_from", dateFrom);
      if (dateTo) params.set("date_to", dateTo);
      if (employeeSearch.trim()) params.set("employee_code", employeeSearch.trim());
      const resp = await fetch(`/api/v1/finance/position-data/export?${params.toString()}`, { credentials: "include" });
      if (!resp.ok) throw new Error(`导出失败 (${resp.status})`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `position-data-${stage || "all"}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (cause: unknown) {
      setError(cause instanceof Error ? cause.message : "导出失败");
    } finally {
      setExporting(false);
    }
  }

  const filteredItems = useMemo(() => items, [items]);

  return (
    <section className="finance-position-page">
      <PageHeader
        title="岗位数据"
        subtitle="按生产岗位查看正式生产记录与检测数据。"
      />

      {error && <ErrorAlert message={error} />}

      {/* ── Filter Bar ── */}
      <div className="filter-bar" style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 16, alignItems: "flex-end" }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: "0.8rem" }}>
          开始日期
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #d1d5db" }} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: "0.8rem" }}>
          结束日期
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #d1d5db" }} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: "0.8rem" }}>
          工厂
          <input type="text" value={factoryId} onChange={(e) => setFactoryId(e.target.value)} placeholder="工厂 ID" style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #d1d5db", width: 100 }} />
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: "0.8rem" }}>
          岗位
          <select value={stage} onChange={(e) => setStage(e.target.value)} style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #d1d5db" }}>
            <option value="">全部岗位</option>
            {STAGE_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
          </select>
        </label>
        <label style={{ display: "flex", flexDirection: "column", gap: 2, fontSize: "0.8rem" }}>
          员工
          <input type="text" value={employeeSearch} onChange={(e) => setEmployeeSearch(e.target.value)} placeholder="工号" style={{ padding: "6px 8px", borderRadius: 6, border: "1px solid #d1d5db", width: 80 }} />
        </label>
        <button type="button" className="btn secondary" onClick={() => void load()} disabled={loading} style={{ padding: "6px 16px" }}>查询</button>
        <button type="button" className="btn primary" onClick={() => void handleExport()} disabled={exporting || items.length === 0} style={{ padding: "6px 16px", background: "#17653a", color: "#fff", border: "none", borderRadius: 6, cursor: "pointer" }}>
          {exporting ? "导出中…" : `导出 XLSX (${items.length})`}
        </button>
      </div>

      {/* ── Summary ── */}
      <div className="summary-row" style={{ marginBottom: 12, fontSize: "0.85rem", color: "#6b7280" }}>
        {loading ? "加载中…" : `共 ${items.length} 条记录${stage ? ` · ${STAGE_LABELS[stage] || stage}` : ""}`}
      </div>

      {/* ── Data Table ── */}
      {loading ? (
        <div className="empty-state">加载中…</div>
      ) : filteredItems.length === 0 ? (
        <div className="empty-state">{stage || factoryId || dateFrom ? "没有匹配的数据" : "请选择筛选条件后查询"}</div>
      ) : (
        <div className="governed-table-wrap">
          <table className="governed-table">
            <thead>
              <tr>
                <th>日期</th>
                <th>工号</th>
                <th>姓名</th>
                <th>工厂</th>
                <th>记录号</th>
                <th>笼号</th>
                <th>工序</th>
                <th>当前状态</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => (
                <tr key={`${item.record_id}-${item.stage}`}>
                  <td>{item.date ? new Date(item.date).toLocaleDateString("zh-CN") : "—"}</td>
                  <td>{item.employee_code}</td>
                  <td>{item.employee_name}</td>
                  <td>{item.factory_id}</td>
                  <td>{item.display_no}</td>
                  <td>{item.cage_no || "—"}</td>
                  <td>{STAGE_LABELS[item.stage] || item.stage}</td>
                  <td>{item.status === "COMPLETED" ? "已完成" : item.current_stage || item.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}
