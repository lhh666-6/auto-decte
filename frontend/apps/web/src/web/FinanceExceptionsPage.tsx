import { useEffect, useState } from "react";

import { listFinanceCorrections, listFinanceLedger } from "./api";
import type { FinanceRecord, SubmissionCorrection } from "./types";
import { DetailDrawer, DetailField, StatusBadge } from "./shared";
import "./finance-pages.css";

interface ExceptionItem {
  id: string;
  severity: "CRITICAL" | "WARNING" | "INFO";
  type: string;
  recordNo: string;
  factoryId: string;
  employeeCode: string;
  discoveredAt: string;
  status: string;
  description: string;
}

const EXCEPTION_TYPE_LABELS: Record<string, string> = {
  MISSING_SOURCE: "缺失来源",
  DUPLICATE_FACT: "重复事实",
  AMOUNT_ANOMALY: "金额异常",
  MISSING_MASTER_DATA: "主数据缺失",
  RULE_VERSION_INAPPLICABLE: "规则版本不适用",
  CONFIRMED_THEN_CHANGED: "已确认后变化",
  EXPORTED_THEN_CORRECTED: "已导出后更正",
  EXPORT_FAILED: "导出失败",
};

function buildExceptions(
  records: FinanceRecord[],
  corrections: SubmissionCorrection[],
): ExceptionItem[] {
  const items: ExceptionItem[] = [];

  for (const c of corrections) {
    items.push({
      id: c.correction_id,
      severity: "WARNING",
      type: c.status === "REPLACED" ? "CONFIRMED_THEN_CHANGED" : "EXPORTED_THEN_CORRECTED",
      recordNo: c.original_submission_id,
      factoryId: c.factory_id,
      employeeCode: "—",
      discoveredAt: c.created_at,
      status: c.status,
      description: c.reason,
    });
  }

  for (const r of records) {
    if (r.status === "ERROR" || r.status === "FAILED") {
      items.push({
        id: r.effective_submission_id,
        severity: "CRITICAL",
        type: "MISSING_SOURCE",
        recordNo: r.effective_submission_id,
        factoryId: r.factory_id,
        employeeCode: r.subject_employee_code,
        discoveredAt: r.submitted_at,
        status: r.status,
        description: "记录缺少有效来源",
      });
    }
    const amt = r.values && typeof r.values === "object" && "amount" in r.values
      ? Number((r.values as Record<string, unknown>).amount)
      : 0;
    if (!Number.isNaN(amt) && amt <= 0 && r.values && "amount" in r.values) {
      items.push({
        id: `AMT_${r.effective_submission_id}`,
        severity: "WARNING",
        type: "AMOUNT_ANOMALY",
        recordNo: r.effective_submission_id,
        factoryId: r.factory_id,
        employeeCode: r.subject_employee_code,
        discoveredAt: r.submitted_at,
        status: r.status,
        description: `金额异常: ${amt}`,
      });
    }
  }

  return items;
}

export function FinanceExceptionsPage() {
  const [exceptions, setExceptions] = useState<ExceptionItem[]>([]);
  const [error, setError] = useState("");
  const [detailId, setDetailId] = useState<string | null>(null);

  function reload() {
    void Promise.all([listFinanceLedger(), listFinanceCorrections()])
      .then(([ledger, corrections]) => {
        setExceptions(buildExceptions(ledger.items, corrections.items));
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "异常数据加载失败");
      });
  }
  useEffect(reload, []);

  const detail = detailId ? exceptions.find((e) => e.id === detailId) : null;

  return (
    <section className="finance-exceptions-page" data-testid="finance-exceptions-page">
      <header>
        <h1 data-testid="finance-page-title">异常记录</h1>
        <p>监控数据一致性、完整性与合规性异常</p>
      </header>
      {error && <div role="alert" className="error-banner">{error}</div>}

      {exceptions.length === 0 ? (
        <div className="finance-exception-empty">
          <p>当前无异常记录。</p>
          <button type="button" onClick={reload}>刷新</button>
        </div>
      ) : (
        <div className="finance-exceptions-list" data-testid="finance-exceptions-table">
          {exceptions.map((item) => (
            <article
              key={item.id}
              className="finance-exception-card"
              onClick={() => setDetailId(item.id)}
              data-testid="finance-exception-detail"
            >
              <span className={`finance-exception-severity ${item.severity}`}>
                {{ CRITICAL: "严重", WARNING: "警告", INFO: "信息" }[item.severity]}
              </span>
              <div className="finance-exception-info">
                <strong>{EXCEPTION_TYPE_LABELS[item.type] ?? item.type}</strong>
                <span>记录号: {item.recordNo} · 工厂: {item.factoryId} · 员工: {item.employeeCode}</span>
                <span>发现时间: {item.discoveredAt}</span>
              </div>
              <div className="finance-exception-status">
                <StatusBadge status={item.status} />
              </div>
            </article>
          ))}
        </div>
      )}

      <DetailDrawer
        open={detail !== null && detail !== undefined}
        onClose={() => setDetailId(null)}
        title={`异常详情 — ${detail?.recordNo ?? ""}`}
      >
        {detail && (
          <div className="finance-detail-section">
            <DetailField label="严重度" value={{ CRITICAL: "严重", WARNING: "警告", INFO: "信息" }[detail.severity]} />
            <DetailField label="异常类型" value={EXCEPTION_TYPE_LABELS[detail.type] ?? detail.type} />
            <DetailField label="记录号" value={detail.recordNo} />
            <DetailField label="工厂" value={detail.factoryId} />
            <DetailField label="员工" value={detail.employeeCode} />
            <DetailField label="发现时间" value={detail.discoveredAt} />
            <DetailField label="状态" value={detail.status} />
            <h3>异常解释</h3>
            <p>{detail.description}</p>
            <h3>影响对象</h3>
            <p>涉及记录 {detail.recordNo}，可能影响关联的工资计算和报表导出。</p>
            <h3>推荐处理</h3>
            <p>请核实来源数据，确认后发起更正或重新导出。</p>
          </div>
        )}
      </DetailDrawer>
    </section>
  );
}
