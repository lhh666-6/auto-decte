import { useEffect, useState } from "react";

import { listOfficialPayroll, listPlantPayroll } from "./api";
import type { BambooPayrollItem, PayrollResult } from "./types";
import "./payroll-pages.css";

function currentMonth() {
  return new Date().toISOString().slice(0, 7);
}

function PlantPayrollResults() {
  const [month, setMonth] = useState(currentMonth());
  const [items, setItems] = useState<BambooPayrollItem[]>([]);
  const [total, setTotal] = useState("0.00");

  useEffect(() => {
    void listPlantPayroll(month).then((result) => {
      setItems(result.items);
      setTotal(result.total_amount);
    });
  }, [month]);

  return (
    <section className="payroll-page">
      <header><h1>本厂工资查询</h1><p>读取竹丝工资事实的财务确认汇总。</p></header>
      <label>月份
        <input type="month" value={month} onChange={(event) => setMonth(event.target.value)} />
      </label>
      <strong>本月合计：¥ {total}</strong>
      <div className="payroll-list">
        {items.map((item) => (
          <article key={item.employee_code}>
            <strong>{item.employee_code}</strong>
            <b>¥ {item.amount}</b>
          </article>
        ))}
      </div>
    </section>
  );
}

function AdminPayrollResults() {
  const [items, setItems] = useState<PayrollResult[]>([]);
  useEffect(() => {
    void listOfficialPayroll("admin").then((result) => setItems(result.items));
  }, []);
  return (
    <section className="payroll-page">
      <header><h1>全局工资查询</h1><p>管理员可查看所有正式工资结果。</p></header>
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

export function PayrollResultsPage({ workspace }: { workspace: "admin" | "plant" }) {
  return workspace === "plant" ? <PlantPayrollResults /> : <AdminPayrollResults />;
}
