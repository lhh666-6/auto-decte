import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  calculatePayroll,
  confirmPayrollBatch,
  createPayrollRule,
  listOfficialPayroll,
  listPayrollBatches,
  listPayrollRules,
  submitPayrollRule,
} from "./api";
import type { PayrollBatch, PayrollResult, PayrollRuleVersion } from "./types";
import "./payroll-pages.css";

export function PayrollRulesPage() {
  const [rules, setRules] = useState<PayrollRuleVersion[]>([]);
  const [batches, setBatches] = useState<PayrollBatch[]>([]);
  const [results, setResults] = useState<PayrollResult[]>([]);
  const [error, setError] = useState("");

  function reload() {
    void Promise.all([
      listPayrollRules(), listPayrollBatches(), listOfficialPayroll("finance"),
    ]).then(([ruleData, batchData, resultData]) => {
      setRules(ruleData.items);
      setBatches(batchData.items);
      setResults(resultData.items);
    }).catch((cause: unknown) => setError(
      cause instanceof Error ? cause.message : "工资数据加载失败",
    ));
  }
  useEffect(reload, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await createPayrollRule({
        rule_key: String(data.get("rule_key")),
        name: String(data.get("name")),
        factory_id: String(data.get("factory_id")),
        position: "WORKER",
        dsl: {
          metric: String(data.get("metric")),
          rate: String(data.get("rate")),
          base: String(data.get("base") || "0"),
        },
      });
      event.currentTarget.reset();
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "规则保存失败");
    }
  }

  async function calculate(rule: PayrollRuleVersion) {
    const today = new Date().toISOString().slice(0, 10);
    try {
      await calculatePayroll(rule.rule_version_id, `${today.slice(0, 7)}-01`, today);
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "计算失败");
    }
  }

  return (
    <section className="payroll-page">
      <header><h1>工资规则与计算</h1><p>规则经管理员批准后才可执行；每个结果固定绑定规则版本和数据水位。</p></header>
      {error && <div role="alert">{error}</div>}
      <form className="payroll-rule-form" onSubmit={create}>
        <label>规则名称<input name="name" required /></label>
        <label>规则标识<input name="rule_key" required /></label>
        <label>工厂<input name="factory_id" required /></label>
        <label>计量字段<input name="metric" placeholder="qualified_quantity" required /></label>
        <label>单价<input name="rate" inputMode="decimal" required /></label>
        <label>基础金额<input name="base" inputMode="decimal" defaultValue="0" /></label>
        <button type="submit">保存工资规则草稿</button>
      </form>
      <h2>规则版本</h2>
      <div className="payroll-list">
        {rules.map((rule) => (
          <article key={rule.rule_version_id}>
            <strong>{rule.name} V{rule.version}</strong>
            <span>{rule.factory_id} · {rule.status} · {rule.dsl.metric} × {rule.dsl.rate}</span>
            {rule.status === "DRAFT" && <button type="button" onClick={() => void submitPayrollRule(rule.rule_version_id).then(reload)}>提交管理员审批</button>}
            {rule.status === "APPROVED" && <button type="button" onClick={() => void calculate(rule)}>按本月计算</button>}
          </article>
        ))}
      </div>
      <h2>计算批次</h2>
      <div className="payroll-list">
        {batches.map((batch) => (
          <article key={batch.batch_id}>
            <strong>{batch.batch_type} · {batch.status}</strong>
            <span>{batch.period_start} 至 {batch.period_end}</span>
            {batch.status === "PENDING_FINANCE" && <button type="button" onClick={() => void confirmPayrollBatch(batch.batch_id).then(reload)}>财务二次确认</button>}
          </article>
        ))}
      </div>
      <h2>正式工资</h2>
      <div className="payroll-list">
        {results.map((result) => <article key={result.result_id}><strong>{result.employee_code}</strong><span>¥ {result.amount}</span></article>)}
      </div>
    </section>
  );
}
