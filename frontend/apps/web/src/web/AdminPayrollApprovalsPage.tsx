import { useEffect, useState } from "react";

import { decidePayrollRule, listPayrollApprovals } from "./api";
import type { PayrollRuleVersion } from "./types";
import "./payroll-pages.css";

export function AdminPayrollApprovalsPage() {
  const [items, setItems] = useState<PayrollRuleVersion[]>([]);
  function reload() {
    void listPayrollApprovals().then((result) => setItems(result.items));
  }
  useEffect(reload, []);
  return (
    <section className="payroll-page">
      <header><h1>工资规则审批</h1><p>批准后规则才具备唯一执行资格。</p></header>
      <div className="payroll-list">
        {items.map((item) => (
          <article key={item.rule_version_id}>
            <strong>{item.name} V{item.version}</strong>
            <span>{item.factory_id} · {item.dsl.metric} × {item.dsl.rate} + {item.dsl.base}</span>
            <div>
              <button type="button" onClick={() => void decidePayrollRule(item.rule_version_id, true).then(reload)}>批准生效</button>
              <button type="button" onClick={() => void decidePayrollRule(item.rule_version_id, false).then(reload)}>退回</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
