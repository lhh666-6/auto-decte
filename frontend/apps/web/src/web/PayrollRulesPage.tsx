import { useEffect, useState } from "react";
import {
  listPayrollRules, createPayrollRule, submitPayrollRule, trialCalculatePayroll,
  listFinanceFactories,
} from "./api";
import type { PayrollRuleVersion } from "./types";
import "./finance-pages.css";

const POSITIONS = [
  { value: "", label: "选择职位" },
  { value: "SORT_OPERATOR", label: "分选工" },
  { value: "DIPPING_OPERATOR", label: "浸胶工" },
  { value: "DRYING_RACK_OPERATOR", label: "干燥工" },
];

const POSITION_FIELDS: Record<string, Array<{ key: string; label: string }>> = {
  SORT_OPERATOR: [
    { key: "bundle_count", label: "把数" }, { key: "length", label: "长度" },
    { key: "effective_grade", label: "最终评级" }, { key: "net_weight", label: "净重" },
    { key: "moisture_average", label: "含水率" },
  ],
  DIPPING_OPERATOR: [
    { key: "glue_gain", label: "上胶量" }, { key: "glue_before_weight", label: "胶前重" },
    { key: "glue_after_weight", label: "胶后重" }, { key: "moisture_average", label: "含水率" },
  ],
  DRYING_RACK_OPERATOR: [
    { key: "rack_count", label: "架数" }, { key: "moisture_average", label: "含水率" },
  ],
};

const STATUS_CN: Record<string, string> = {
  DRAFT: "草稿", PENDING_APPROVAL: "待审批", APPROVED: "已生效",
  REJECTED: "已驳回", RETIRED: "历史版本",
};

export function PayrollRulesPage() {
  const [rules, setRules] = useState<PayrollRuleVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");

  const [factories, setFactories] = useState<Array<{ factory_id: string; factory_name: string }>>([]);
  const [factoryId, setFactoryId] = useState("");
  const [position, setPosition] = useState("");
  const [field, setField] = useState("");
  const [rate, setRate] = useState("");
  const [ruleName, setRuleName] = useState("");
  const [submitting, setSubmitting] = useState(false);

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

  async function handleCreate() {
    if (!factoryId || !position || !field || !rate || !ruleName) return;
    setSubmitting(true); setError(""); setMsg("");
    try {
      await createPayrollRule({
        rule_key: `PAYROLL_${factoryId}_${position}`,
        factory_id: factoryId, name: ruleName, position,
        dsl: { metric: field, rate, base: "0" },
      });
      setMsg("规则已创建"); setFactoryId(""); setPosition(""); setField(""); setRate(""); setRuleName("");
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

  const fields = position ? POSITION_FIELDS[position] || [] : [];
  const fieldLabel = fields.find(f => f.key === field)?.label || field;
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
            {factories.map(f => <option key={f.factory_id} value={f.factory_id}>{f.factory_name}</option>)}</select></label>
          <label>职位<select value={position} onChange={e => { setPosition(e.target.value); setField(""); }}>
            {POSITIONS.map(p => <option key={p.value} value={p.value}>{p.label}</option>)}</select></label>
          {fields.length > 0 && <label>计薪依据<select value={field} onChange={e => setField(e.target.value)}>
            <option value="">— 选择 —</option>{fields.map(f => <option key={f.key} value={f.key}>{f.label}</option>)}</select></label>}
          <label>单价 (元)<input type="number" step="0.01" value={rate} onChange={e => setRate(e.target.value)} placeholder="0.35" style={{ maxWidth: 120 }} /></label>
          <label>名称<input type="text" value={ruleName} onChange={e => setRuleName(e.target.value)} placeholder="分选标准计件" style={{ maxWidth: 160 }} /></label>
        </div>
        {formulaPreview && <p className="bp-card" style={{ margin: ".6rem 0", padding: ".5rem .8rem", fontSize: ".9rem", background: "#f0fdf4" }}><strong>预览:</strong> {formulaPreview}</p>}
        <button type="button" className="primary-button" disabled={submitting || !factoryId || !position || !field || !rate} onClick={() => void handleCreate()}>
          {submitting ? "创建中…" : "创建规则"}</button>
      </div>

      <h3 style={{ marginTop: "1.2rem" }}>现有规则</h3>
      {loading ? <div className="page-loading">加载中…</div>
      : rules.length === 0 ? <div className="ledger-empty"><p>暂无工资规则</p></div>
      : <div className="ledger-table-wrap"><table className="ledger-table"><thead><tr><th>名称</th><th>职位</th><th>公式</th><th>状态</th><th>操作</th></tr></thead><tbody>
        {rules.map(r => {
          const fl = Object.values(POSITION_FIELDS).flat().find(f => f.key === r.dsl.metric)?.label || r.dsl.metric;
          return <tr key={r.rule_version_id}>
            <td>{r.name || r.rule_key}</td>
            <td>{POSITIONS.find(p => p.value === r.position)?.label || r.position || "—"}</td>
            <td>{fl} × {r.dsl.rate} 元</td>
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
