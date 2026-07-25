import { useEffect, useState } from "react";
import {
  listPayrollRules, createPayrollRule, submitPayrollRule, trialCalculatePayroll,
  listFinanceFactories, listPayrollFields,
} from "./api";
import type { PayrollRuleVersion } from "./types";
import type { PayrollFieldInfo, FinanceFactoryInfo } from "./api";
import "./finance-pages.css";

const POSITIONS = [
  { value: "", label: "选择职位" },
  { value: "SORT_OPERATOR", label: "分选工" },
  { value: "DIPPING_OPERATOR", label: "浸胶工" },
  { value: "DRYING_RACK_OPERATOR", label: "干燥工" },
];

const STATUS_CN: Record<string, string> = {
  DRAFT: "草稿", PENDING_APPROVAL: "待审批", APPROVED: "已生效",
  REJECTED: "已驳回", RETIRED: "历史版本",
};

export function PayrollRulesPage() {
  const [rules, setRules] = useState<PayrollRuleVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const [factories, setFactories] = useState<FinanceFactoryInfo[]>([]);
  const [factoryId, setFactoryId] = useState("");
  const [position, setPosition] = useState("");
  const [payrollFields, setPayrollFields] = useState<PayrollFieldInfo[]>([]);
  const [field, setField] = useState("");
  const [rate, setRate] = useState("");
  const [ruleName, setRuleName] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Grade lookup state
  const [gradeField, setGradeField] = useState<PayrollFieldInfo | null>(null);
  const [gradeA, setGradeA] = useState("1.00");
  const [gradeB, setGradeB] = useState("0.80");

  const [trialOpen, setTrialOpen] = useState(false);
  const [trialResult, setTrialResult] = useState<{ items: Array<{ employee_code: string; amount: string }>; count: number } | null>(null);

  function reload() {
    setLoading(true);
    listPayrollRules().then(d => { setRules(d.items); setLoading(false); })
      .catch(c => { setError(c instanceof Error ? c.message : "加载失败"); setLoading(false); });
  }
  useEffect(reload, []);

  useEffect(() => {
    listFinanceFactories()
      .then(d => setFactories(d.items))
      .catch(() => {});
  }, []);

  // Load payroll fields from API when position changes
  useEffect(() => {
    if (!position) { setPayrollFields([]); setGradeField(null); setField(""); return; }
    listPayrollFields(position)
      .then(d => {
        setPayrollFields(d.items);
        const lookupDim = d.items.find(f => f.usage === "LOOKUP_DIMENSION");
        setGradeField(lookupDim || null);
        setField("");
      })
      .catch(() => { setPayrollFields([]); setGradeField(null); });
  }, [position]);

  async function handleCreate() {
    if (!factoryId || !position || !field || !rate || !ruleName) return;
    setSubmitting(true); setError(""); setMsg("");
    try {
      const dsl: { metric: string; rate: string; base: string; lookup?: { field: string; values: Record<string, string> } } = {
        metric: field, rate, base: "0",
      };
      if (gradeField && (gradeA || gradeB)) {
        dsl.lookup = { field: gradeField.field_key, values: {} };
        if (gradeA) dsl.lookup.values["A"] = gradeA;
        if (gradeB) dsl.lookup.values["B"] = gradeB;
      }
      await createPayrollRule({
        rule_key: `PAYROLL_${factoryId}_${position}`,
        factory_id: factoryId, name: ruleName, position,
        dsl,
      });
      setMsg("规则已创建"); setFactoryId(""); setPosition(""); setField(""); setRate(""); setRuleName("");
      setGradeA("1.00"); setGradeB("0.80");
      reload();
    } catch (c) { setError(c instanceof Error ? c.message : "创建失败"); }
    finally { setSubmitting(false); }
  }

  async function handleSubmit(rule: PayrollRuleVersion) {
    try { await submitPayrollRule(rule.rule_version_id); setMsg("已提交审批"); reload(); }
    catch (c) { setError(c instanceof Error ? c.message : "提交失败"); }
  }

  async function handleTrial(rule: PayrollRuleVersion) {
    setTrialOpen(true); setTrialResult(null);
    try {
      const now = new Date();
      const start = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().slice(0, 10);
      const end = now.toISOString().slice(0, 10);
      const r = await trialCalculatePayroll(rule.rule_version_id, start, end);
      setTrialResult({ items: r.items, count: r.result_count });
    } catch (c) { setError(c instanceof Error ? c.message : "试算失败"); }
  }

  const metricFields = payrollFields.filter(f => f.usage === "NUMERIC_METRIC");
  const fieldLabel = metricFields.find(f => f.field_key === field)?.display_name || field;
  const formulaPreview = field && rate ? `工资 = ${fieldLabel} × ${rate} 元` : "";

  return (
    <section className="ledger-page">
      <header><h1>工资规则</h1><p>按职位配置工资计算公式，使用正式业务字段。</p></header>
      {error && <div className="ledger-error">{error}<button type="button" onClick={() => setError("")}>✕</button></div>}
      {msg && <div className="ledger-success">{msg}<button type="button" onClick={() => setMsg("")}>✕</button></div>}

      <div className="bp-card">
        <h3 style={{ margin: "0 0 .8rem", fontSize: "1rem" }}>新建工资规则</h3>
        <div className="ledger-filters">
          <label>工厂<select value={factoryId} onChange={e => setFactoryId(e.target.value)}>
            <option value="">选择工厂</option>
            {factories.map(f => <option key={f.factory_id} value={f.factory_id}>{f.name}</option>)}</select></label>
          <label>职位<select value={position} onChange={e => { setPosition(e.target.value); setField(""); }}>
            {POSITIONS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}</select></label>
          {metricFields.length > 0 && <label>计薪依据<select value={field} onChange={e => setField(e.target.value)}>
            <option value="">— 选择 —</option>{metricFields.map(f => <option key={f.field_key} value={f.field_key}>{f.display_name}</option>)}</select></label>}
          <label>单价 (元)<input type="number" step="0.01" value={rate} onChange={e => setRate(e.target.value)} placeholder="0.35" style={{ maxWidth: 120 }} /></label>
          <label>名称<input type="text" value={ruleName} onChange={e => setRuleName(e.target.value)} placeholder="分选标准计件" style={{ maxWidth: 160 }} /></label>
        </div>
        {gradeField && (
          <div className="bp-card" style={{ margin: ".6rem 0", padding: ".5rem .8rem", background: "#fefce8" }}>
            <p style={{ margin: "0 0 .4rem", fontSize: ".85rem", fontWeight: 600 }}>评级调整 ({gradeField.display_name})</p>
            <div className="ledger-filters">
              <label>A 级系数<input type="number" step="0.01" value={gradeA} onChange={e => setGradeA(e.target.value)} placeholder="1.00" style={{ maxWidth: 100 }} /></label>
              <label>B 级系数<input type="number" step="0.01" value={gradeB} onChange={e => setGradeB(e.target.value)} placeholder="0.80" style={{ maxWidth: 100 }} /></label>
            </div>
          </div>
        )}
        {formulaPreview && <p className="bp-card" style={{ margin: ".6rem 0", padding: ".5rem .8rem", fontSize: ".9rem", background: "#f0fdf4" }}><strong>预览:</strong> {formulaPreview}{gradeField && ` × ${gradeField.display_name}系数`}</p>}
        <button type="button" className="primary-button" disabled={submitting || !factoryId || !position || !field || !rate} onClick={() => void handleCreate()}>
          {submitting ? "创建中…" : "创建规则"}</button>
      </div>

      <h3 style={{ marginTop: "1.2rem" }}>现有规则</h3>
      {loading ? <div className="page-loading">加载中…</div>
      : rules.length === 0 ? <div className="ledger-empty"><p>暂无工资规则</p></div>
      : <div className="ledger-table-wrap"><table className="ledger-table"><thead><tr><th>名称</th><th>职位</th><th>公式</th><th>状态</th><th>操作</th></tr></thead><tbody>
        {rules.map(r => {
          const fl = metricFields.find(f => f.field_key === r.dsl.metric)?.display_name || r.dsl.metric;
          const lookupKey = r.dsl["lookup.field"];
          const hasLookup = !!lookupKey;
          const lookupLabel = payrollFields.find(f => f.field_key === lookupKey)?.display_name || lookupKey;
          return <tr key={r.rule_version_id}>
            <td>{r.name || r.rule_key}</td>
            <td>{POSITIONS.find(p => p.value === r.position)?.label || r.position || "—"}</td>
            <td>{fl} x {r.dsl.rate} 元{hasLookup ? ` x ${lookupLabel}系数` : ""}</td>
            <td><span className={`ledger-tag ${r.status === "APPROVED" ? "" : "ledger-tag-alert"}`}>{STATUS_CN[r.status] || r.status}</span></td>
            <td>{r.status === "DRAFT" && <button type="button" className="primary-button" style={{ marginRight: 6 }} onClick={() => void handleSubmit(r)}>提交审批</button>}
              <button type="button" className="secondary-button" onClick={() => void handleTrial(r)}>试算</button></td>
          </tr>;
        })}
      </tbody></table></div>}

      {trialOpen && (
        <div className="ledger-modal-overlay" onClick={() => setTrialOpen(false)}>
          <div className="ledger-modal" onClick={e => e.stopPropagation()} style={{ maxWidth: 420 }}>
            <header><h2>工资试算</h2><button type="button" className="secondary-button" onClick={() => setTrialOpen(false)}>✕</button></header>
            {trialResult ? <div>
              <div className="disposition-summary">
                <p><strong>试算结果:</strong> {trialResult.count} 条记录</p>
                {trialResult.items.slice(0, 5).map((it, i) => (
                  <p key={i} className="signature-muted">{it.employee_code}: ¥ {Number(it.amount).toLocaleString()}</p>
                ))}
                {trialResult.items.length > 5 && <p className="signature-muted">…等 {trialResult.count} 条</p>}
              </div>
              <p className="signature-muted" style={{ marginTop: ".5rem" }}>确认无误后请提交管理员审批。</p>
            </div> : <p className="signature-muted">正在计算…</p>}
          </div>
        </div>
      )}
    </section>
  );
}
