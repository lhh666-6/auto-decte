import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { getOverview, getFinanceLedgerOverview, listFinanceCorrections, listGovernedExports, listPayrollBatches } from "./api";
import type { WorkspaceOverview, GovernedExportBatch, PayrollBatch, SubmissionCorrection } from "./types";

interface FinanceOverviewData {
  officialRecords: number;
  officialRecordsMonth: number;
  exceptions: number | null;
  pendingCorrections: number;
  pendingReview: number;
  needReExport: number;
  recentBatches: PayrollBatch[];
  recentExports: GovernedExportBatch[];
}

function kpiValue(v: number | null): string {
  if (v === null || v === undefined) return "—";
  return String(v);
}

export function FinanceOverviewEnhancement() {
  const navigate = useNavigate();
  const [base, setBase] = useState<WorkspaceOverview | null>(null);
  const [data, setData] = useState<FinanceOverviewData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([
      getOverview("finance"),
      getFinanceLedgerOverview(),
      listFinanceCorrections(),
      listPayrollBatches(),
      listGovernedExports(),
    ])
      .then(([overview, ledgerSum, correctionsRes, batchesRes, exportsRes]) => {
        if (!active) return;
        setBase(overview);
        setData({
          officialRecords: ledgerSum.today,
          officialRecordsMonth: ledgerSum.month,
          exceptions: null, // no dedicated exceptions API yet; real data requires separate endpoint
          pendingCorrections: correctionsRes.items.filter(
            (c: SubmissionCorrection) => c.status === "RETURNED",
          ).length,
          pendingReview: correctionsRes.items.filter(
            (c: SubmissionCorrection) => c.status === "REPLACED",
          ).length,
          needReExport: exportsRes.items.filter(
            (e: GovernedExportBatch) => e.status === "FAILED" || e.status === "EXPIRED",
          ).length,
          recentBatches: batchesRes.items.slice(0, 3),
          recentExports: exportsRes.items.slice(0, 3),
        });
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : "概览加载失败");
      });
    return () => { active = false; };
  }, []);

  function go(path: string) {
    navigate(path);
  }

  if (error) return <div role="alert" className="error-banner">{error}</div>;
  if (!base || !data) return <div role="status">正在加载财务概览…</div>;

  return (
    <section className="finance-overview-page">
      <h1>{base.title}</h1>
      {base.factory_name && <p className="finance-overview-factory">{base.factory_name}</p>}

      <div className="finance-overview-main-cards">
        <button type="button" className="finance-overview-main-card" onClick={() => go("/finance/today")}>
          <span className="finance-overview-main-card-value">{kpiValue(data.officialRecords)}</span>
          <span className="finance-overview-main-card-label">今日正式记录</span>
        </button>
        <button type="button" className="finance-overview-main-card" onClick={() => go("/finance/exceptions")}>
          <span className="finance-overview-main-card-value alert">{kpiValue(data.exceptions)}</span>
          <span className="finance-overview-main-card-label">诊断</span>
        </button>
        <button type="button" className="finance-overview-main-card" onClick={() => go("/finance/exceptions")}>
          <span className="finance-overview-main-card-value">{kpiValue(data.pendingCorrections)}</span>
          <span className="finance-overview-main-card-label">待重新填报更正</span>
        </button>
        <button type="button" className="finance-overview-main-card" onClick={() => go("/finance/today")}>
          <span className="finance-overview-main-card-value">{kpiValue(data.pendingReview)}</span>
          <span className="finance-overview-main-card-label">待财务复核</span>
        </button>
      </div>

      <div className="finance-overview-secondary">
        <div className="finance-overview-section">
          <h2>最近工资批次</h2>
          {data.recentBatches.length === 0 ? (
            <p className="finance-overview-empty">暂无正式工资批次</p>
          ) : (
            <div className="finance-overview-list">
              {data.recentBatches.map((b) => (
                <div key={b.batch_id} className="finance-overview-list-item">
                  <span>{b.batch_type}</span>
                  <span>{b.status}</span>
                  <button type="button" onClick={() => go("/finance/payroll-rules")}>查看</button>
                </div>
              ))}
            </div>
          )}
          <button type="button" className="finance-overview-section-link" onClick={() => go("/finance/payroll-rules")}>
            前往工资规则
          </button>
        </div>
        <div className="finance-overview-section">
          <h2>最近导出</h2>
          {data.recentExports.length === 0 ? (
            <p className="finance-overview-empty">暂无正式导出</p>
          ) : (
            <div className="finance-overview-list">
              {data.recentExports.map((e) => (
                <div key={e.export_batch_id} className="finance-overview-list-item">
                  <span>{e.download_name || e.export_batch_id}</span>
                  <span>{e.status}</span>
                </div>
              ))}
            </div>
          )}
          <button type="button" className="finance-overview-section-link" onClick={() => go("/finance/exports")}>
            前往报表导出
          </button>
        </div>
      </div>
    </section>
  );
}
