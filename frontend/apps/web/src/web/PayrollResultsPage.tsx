import { useEffect, useState } from "react";

import { listOfficialPayroll } from "./api";
import type { PayrollResult } from "./types";
import "./payroll-pages.css";

export function PayrollResultsPage({ workspace }: { workspace: "admin" | "plant" }) {
  const [items, setItems] = useState<PayrollResult[]>([]);
  useEffect(() => {
    void listOfficialPayroll(workspace).then((result) => setItems(result.items));
  }, [workspace]);
  return (
    <section className="payroll-page">
      <header><h1>{workspace === "admin" ? "全局工资查询" : "本厂工资查询"}</h1><p>仅显示财务已确认的正式工资，所有查看均写入审计。</p></header>
      <div className="payroll-list">
        {items.map((item) => (
          <article key={item.result_id}>
            <strong>{item.employee_code}</strong>
            <span>{item.factory_id} · {item.business_date}</span>
            <b>¥ {item.amount}</b>
          </article>
        ))}
      </div>
    </section>
  );
}
