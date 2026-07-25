import { useCallback, useEffect, useMemo, useState } from "react";

interface PositionDataItem {
  record_id: string; display_no: string; form_type: string;
  factory_id: string; date: string; employee_code: string;
  employee_name: string; stage: string; cage_no: string;
  values: Record<string, unknown>; status: string; current_stage: string;
}

interface FactoryInfo { factory_id: string; code: string; name: string; }

const POSITIONS = [
  { value: "", label: "全部岗位" },
  { value: "SORT", label: "分选工" },
  { value: "DIPPING", label: "浸胶工" },
  { value: "DRYING", label: "干燥工" },
];

/* Per-position column definitions */
const SORT_COLUMNS = ["日期","员工","笼号","把数","长度","深浅","品级","最终评级","净重","含水率","状态"];
const DIP_COLUMNS  = ["日期","员工","笼号","胶前重","胶后重","上胶量","胶液批次","浸胶开始","浸胶结束","含水率","最终评级"];
const DRY_COLUMNS  = ["日期","员工","笼号","干燥架号","架数","干燥开始","干燥结束","含水率","最终评级"];
const ALL_COLUMNS  = ["日期","工号","姓名","岗位","笼号","表号","状态"];

function columnsFor(stage: string): string[] {
  if (stage === "SORT") return SORT_COLUMNS;
  if (stage === "DIPPING") return DIP_COLUMNS;
  if (stage === "DRYING") return DRY_COLUMNS;
  return ALL_COLUMNS;
}

function extractVal(v: Record<string, unknown>, key: string): string {
  const m: Record<string, string[]> = {
    把数: ["bundle_count"], 长度: ["length"], 深浅: ["shade"],
    品级: ["grade"], 最终评级: ["effective_grade","grade"],
    净重: ["net_weight"], 含水率: ["moisture_average","moisture"],
    胶前重: ["glue_before_weight"], 胶后重: ["glue_after_weight"],
    上胶量: ["glue_gain"], 胶液批次: ["glue_batch"],
    浸胶开始: ["dipping_start"], 浸胶结束: ["dipping_end"],
    干燥架号: ["rack_numbers"], 架数: ["rack_count"],
    干燥开始: ["drying_start"], 干燥结束: ["drying_end"],
  };
  const keys = m[key] || [key];
  for (const k of keys) {
    const raw = v[k];
    if (raw !== undefined && raw !== null && raw !== "") {
      if (Array.isArray(raw)) return raw.join(", ");
      return String(raw);
    }
  }
  return "—";
}

export function FinancePositionDataPage() {
  const [items, setItems] = useState<PositionDataItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [factories, setFactories] = useState<FactoryInfo[]>([]);
  const [factoryId, setFactoryId] = useState("");
  const [stage, setStage] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [employeeSearch, setEmployeeSearch] = useState("");
  const [exporting, setExporting] = useState(false);

  useEffect(() => {
    fetch("/api/v1/admin/factories", { credentials: "include" })
      .then((r) => r.json())
      .then((d: { factories?: FactoryInfo[] }) => setFactories(d.factories ?? []))
      .catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError("");
    try {
      const p = new URLSearchParams();
      if (factoryId) p.set("factory_id", factoryId);
      if (stage) p.set("stage", stage);
      if (dateFrom) p.set("date_from", dateFrom);
      if (dateTo) p.set("date_to", dateTo);
      if (employeeSearch.trim()) p.set("employee_code", employeeSearch.trim());
      const r = await fetch(`/api/v1/finance/position-data?${p.toString()}`, { credentials: "include" });
      if (!r.ok) throw new Error(`请求失败 (${r.status})`);
      const d = (await r.json()) as { items: PositionDataItem[] };
      setItems(d.items ?? []);
    } catch (c: unknown) { setError(c instanceof Error ? c.message : "数据加载失败"); }
    finally { setLoading(false); }
  }, [factoryId, stage, dateFrom, dateTo, employeeSearch]);
  useEffect(() => { void load(); }, [load]);

  async function handleExport() {
    setExporting(true);
    try {
      const p = new URLSearchParams();
      if (factoryId) p.set("factory_id", factoryId);
      if (stage) p.set("stage", stage);
      if (dateFrom) p.set("date_from", dateFrom);
      if (dateTo) p.set("date_to", dateTo);
      if (employeeSearch.trim()) p.set("employee_code", employeeSearch.trim());
      const r = await fetch(`/api/v1/finance/position-data/export?${p.toString()}`, { credentials: "include" });
      if (!r.ok) throw new Error(`导出失败 (${r.status})`);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a"); a.href = url;
      a.download = `position-data-${stage || "all"}.xlsx`; a.click();
      URL.revokeObjectURL(url);
    } catch (c: unknown) { setError(c instanceof Error ? c.message : "导出失败"); }
    finally { setExporting(false); }
  }

  const cols = useMemo(() => columnsFor(stage), [stage]);

  return (
    <section className="ledger-page">
      <header>
        <h1>岗位数据</h1>
        <p>按工厂、岗位、日期查看生产业务数据，支持按岗位导出 XLSX。</p>
      </header>

      {error && <div className="ledger-error">{error}<button type="button" onClick={() => setError("")}>✕</button></div>}

      <div className="ledger-filters">
        <label>工厂
          <select value={factoryId} onChange={(e) => setFactoryId(e.target.value)}>
            <option value="">全部工厂</option>
            {factories.map((f) => <option key={f.factory_id} value={f.factory_id}>{f.name}</option>)}
          </select>
        </label>
        <label>岗位
          <select value={stage} onChange={(e) => setStage(e.target.value)}>
            {POSITIONS.map((p) => <option key={p.value} value={p.value}>{p.label}</option>)}
          </select>
        </label>
        <label>开始日期
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>结束日期
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        <label>员工
          <input type="text" value={employeeSearch} onChange={(e) => setEmployeeSearch(e.target.value)} placeholder="工号或姓名" />
        </label>
        <button type="button" onClick={load}>查询</button>
        <button type="button" onClick={() => void handleExport()} disabled={exporting} className="primary-button">
          {exporting ? "导出中…" : "↓ 导出 Excel"}
        </button>
      </div>

      {loading ? (
        <div className="page-loading">加载中…</div>
      ) : items.length === 0 ? (
        <div className="ledger-empty">
          <p><strong>暂无数据</strong></p>
          <p className="signature-muted">请选择筛选条件后点击"查询"。</p>
        </div>
      ) : (
        <div className="ledger-table-wrap">
          <table className="ledger-table">
            <thead>
              <tr>
                {cols.map((c) => <th key={c}>{c}</th>)}
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => (
                <tr key={item.record_id || i}>
                  {cols.map((c) => {
                    if (c === "日期") return <td key={c}>{item.date || "—"}</td>;
                    if (c === "员工") return <td key={c}>{item.employee_name} <span className="signature-muted">{item.employee_code}</span></td>;
                    if (c === "工号") return <td key={c}>{item.employee_code}</td>;
                    if (c === "姓名") return <td key={c}>{item.employee_name}</td>;
                    if (c === "岗位") return <td key={c}>{POSITIONS.find(p=>p.value===item.stage)?.label ?? item.stage}</td>;
                    if (c === "笼号") return <td key={c}>{item.cage_no || "—"}</td>;
                    if (c === "表号") return <td key={c}>{item.display_no}</td>;
                    if (c === "状态") return <td key={c}>{item.status}</td>;
                    return <td key={c}>{extractVal(item.values, c)}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
          <p className="signature-muted" style={{ marginTop: 8 }}>共 {items.length} 条记录</p>
        </div>
      )}
    </section>
  );
}
