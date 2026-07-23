import { useEffect, useState } from "react";

import {
  listFinanceCorrections,
  listFinanceLedger,
  getFinanceLedgerOverview,
  reviewCorrection,
} from "./api";
import type { FinanceRecord, SubmissionCorrection } from "./types";
import "./ledger-pages.css";

export function FinanceLedgerPage() {
  const [overview, setOverview] = useState({ today: 0, month: 0, year: 0 });
  const [records, setRecords] = useState<FinanceRecord[]>([]);
  const [corrections, setCorrections] = useState<SubmissionCorrection[]>([]);
  const [error, setError] = useState("");

  function reload() {
    void Promise.all([
      getFinanceLedgerOverview(),
      listFinanceLedger(),
      listFinanceCorrections(),
    ]).then(([summary, ledger, cases]) => {
      setOverview(summary);
      setRecords(ledger.items);
      setCorrections(cases.items);
    }).catch((cause: unknown) => setError(
      cause instanceof Error ? cause.message : "账本加载失败",
    ));
  }

  useEffect(reload, []);

  async function decide(correctionId: string, approved: boolean) {
    try {
      await reviewCorrection(correctionId, approved, approved ? "财务复核通过" : "财务复核退回");
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "复核失败");
    }
  }

  return (
    <section className="ledger-page">
      <header><h1>实时财务账本</h1><p>按北京时间归属自然日；更正保留原始记录和完整替换链。</p></header>
      {error && <div role="alert" className="error-banner">{error}</div>}
      <div className="ledger-summary">
        <article><span>今日有效提交</span><strong>{overview.today}</strong></article>
        <article><span>本月有效提交</span><strong>{overview.month}</strong></article>
        <article><span>本年有效提交</span><strong>{overview.year}</strong></article>
      </div>
      <h2>当前有效记录</h2>
      <div className="ledger-table-wrap">
        <table>
          <thead><tr><th>业务日期</th><th>工厂</th><th>员工</th><th>提交号</th><th>状态</th><th>数据</th></tr></thead>
          <tbody>
            {records.map((record) => (
              <tr key={record.root_submission_id}>
                <td>{record.business_date}</td><td>{record.factory_id}</td>
                <td>{record.subject_employee_code}</td><td>{record.effective_submission_id}</td>
                <td>{record.status}</td><td>{JSON.stringify(record.values)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <h2>更正复核</h2>
      <div className="ledger-case-list">
        {corrections.map((item) => (
          <article key={item.correction_id}>
            <strong>{item.original_submission_id} · {item.status}</strong>
            <span>{item.reason}</span>
            {item.status === "REPLACED" && (
              <div>
                <button type="button" onClick={() => void decide(item.correction_id, true)}>复核通过</button>
                <button type="button" onClick={() => void decide(item.correction_id, false)}>退回复核</button>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
