import { useEffect, useState } from "react";

import { getPlantProduction, returnPlantSubmission } from "./api";
import type { FinanceRecord } from "./types";
import "./ledger-pages.css";

export function PlantProductionPage() {
  const [records, setRecords] = useState<FinanceRecord[]>([]);
  const [overview, setOverview] = useState({ today: 0, month: 0, year: 0 });
  const [selected, setSelected] = useState<FinanceRecord | null>(null);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  function reload() {
    void getPlantProduction().then((result) => {
      setRecords(result.records);
      setOverview(result.overview);
    }).catch((cause: unknown) => setError(
      cause instanceof Error ? cause.message : "生产数据加载失败",
    ));
  }
  useEffect(reload, []);

  async function submitReturn() {
    if (!selected || !reason.trim()) return;
    try {
      await returnPlantSubmission(
        selected.effective_submission_id,
        reason,
        selected.subject_employee_code,
      );
      setSelected(null);
      setReason("");
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "打回失败");
    }
  }

  return (
    <section className="ledger-page">
      <header><h1>本厂生产看板</h1><p>只显示本厂当前有效记录；打回后形成员工重填待办。</p></header>
      {error && <div role="alert">{error}</div>}
      <div className="ledger-summary">
        <article><span>今日</span><strong>{overview.today}</strong></article>
        <article><span>本月</span><strong>{overview.month}</strong></article>
        <article><span>本年</span><strong>{overview.year}</strong></article>
      </div>
      <div className="ledger-case-list">
        {records.map((record) => (
          <article key={record.root_submission_id}>
            <strong>{record.subject_employee_code} · {record.business_date}</strong>
            <span>{record.effective_submission_id} · {record.status}</span>
            <button type="button" onClick={() => setSelected(record)}>打回重填</button>
          </article>
        ))}
      </div>
      {selected && (
        <div className="ledger-return-panel">
          <h2>打回 {selected.effective_submission_id}</h2>
          <label>打回原因<textarea aria-label="打回原因" value={reason} onChange={(event) => setReason(event.target.value)} /></label>
          <button type="button" disabled={!reason.trim()} onClick={() => void submitReturn()}>确认打回</button>
          <button type="button" onClick={() => setSelected(null)}>取消</button>
        </div>
      )}
    </section>
  );
}
