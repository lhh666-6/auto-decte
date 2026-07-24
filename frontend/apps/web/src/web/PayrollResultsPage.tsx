import { useEffect, useMemo, useState } from "react";

import { listOfficialPayroll, listPlantPayroll } from "./api";
import type { BambooPayrollItem, PayrollResult } from "./types";
import "./payroll-pages.css";

/** Business timezone (Asia/Shanghai) month string. */
function currentMonth(): string {
  const now = new Date();
  // Offset to Asia/Shanghai: UTC+8
  const shanghai = new Date(now.getTime() + 8 * 60 * 60 * 1000);
  return shanghai.toISOString().slice(0, 7);
}

function PlantPayrollResults() {
  const [month, setMonth] = useState(currentMonth());
  const [items, setItems] = useState<BambooPayrollItem[]>([]);
  const [total, setTotal] = useState("0.00");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [employeeFilter, setEmployeeFilter] = useState("");

  function load() {
    setLoading(true);
    setError("");
    listPlantPayroll(month)
      .then((result) => {
        setItems(result.items);
        setTotal(result.total_amount);
        setLoading(false);
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "工资数据加载失败");
        // Do NOT show ¥0.00 on error
        setTotal("");
        setItems([]);
        setLoading(false);
      });
  }
  useEffect(load, [month]);

  const filteredItems = useMemo(() => {
    if (!employeeFilter.trim()) return items;
    const q = employeeFilter.trim().toLowerCase();
    return items.filter((item) => item.employee_code.toLowerCase().includes(q));
  }, [items, employeeFilter]);

  return (
    <section className="payroll-page">
      <header><h1>本厂工资查询</h1><p>读取竹丝工资事实的财务确认汇总。</p></header>
      <label>
        月份
        <input type="month" value={month} onChange={(event) => setMonth(event.target.value)} />
      </label>
      <label>
        搜索员工
        <input
          type="search"
          value={employeeFilter}
          onChange={(event) => setEmployeeFilter(event.target.value)}
          placeholder="输入工号搜索…"
        />
      </label>
      {loading && <div role="status">正在加载工资数据…</div>}
      {error && <div role="alert">{error} <button type="button" onClick={load}>重试</button></div>}
      {!loading && !error && (
        <strong>本月合计：¥ {total || "—"}</strong>
      )}
      {!loading && !error && (
        <div className="payroll-list">
          {filteredItems.map((item) => (
            <article key={item.employee_code}>
              <strong>{item.employee_code}</strong>
              <b>¥ {item.amount}</b>
            </article>
          ))}
          {filteredItems.length === 0 && items.length > 0 && (
            <p className="signature-muted">没有匹配的员工记录。</p>
          )}
        </div>
      )}
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
