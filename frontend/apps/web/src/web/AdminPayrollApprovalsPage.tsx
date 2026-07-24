import { useCallback, useEffect, useMemo, useState } from "react";

import { decidePayrollRule, listPayrollApprovals } from "./api";
import { VersionDiffPanel } from "./shared/VersionDiffPanel";
import type { DiffRuleLine } from "./shared/VersionDiffPanel";
import { ReasonConfirmDialog } from "./shared/ReasonConfirmDialog";
import type { ImpactScope, PreCheckResult } from "./shared/ReasonConfirmDialog";
import type { PayrollRuleVersion } from "./types";
import "./payroll-pages.css";
import "./workspace.css";

/* ------------------------------------------------------------------ */
/*  helpers                                                            */
/* ------------------------------------------------------------------ */

function buildRuleDiff(
  current: PayrollRuleVersion,
  _previous?: PayrollRuleVersion,
): DiffRuleLine[] {
  const lines: DiffRuleLine[] = [
    { key: "指标 (metric)", oldValue: _previous?.dsl.metric ?? "-", newValue: current.dsl.metric },
    { key: "单价 (rate)", oldValue: _previous?.dsl.rate ?? "-", newValue: current.dsl.rate },
    { key: "底薪 (base)", oldValue: _previous?.dsl.base ?? "-", newValue: current.dsl.base },
  ];
  return lines;
}

function buildPreCheck(item: PayrollRuleVersion): PreCheckResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!item.dsl.metric) {
    errors.push("计算指标 (metric) 未指定");
  }
  const rate = parseFloat(item.dsl.rate);
  if (item.dsl.rate && (isNaN(rate) || rate <= 0)) {
    errors.push("单价 (rate) 无效或非正数");
  }

  return { passed: errors.length === 0, errors, warnings };
}

/** Mock trial-calculation samples for demonstration. */
interface TrialSample {
  employee_code: string;
  metric_value: number;
  old_amount: string;
  new_amount: string;
  delta: string;
}

function buildTrialSamples(current: PayrollRuleVersion): TrialSample[] {
  const rate = parseFloat(current.dsl.rate) || 0;
  const base = parseFloat(current.dsl.base) || 0;
  const employees = ["EMP001", "EMP002", "EMP003"];
  return employees.map((code, i) => {
    const metric = (i + 1) * 100;
    const oldAmount = metric * (rate * 0.9) + base;
    const newAmount = metric * rate + base;
    const delta = newAmount - oldAmount;
    return {
      employee_code: code,
      metric_value: metric,
      old_amount: oldAmount.toFixed(2),
      new_amount: newAmount.toFixed(2),
      delta: (delta >= 0 ? "+" : "") + delta.toFixed(2),
    };
  });
}

/* ------------------------------------------------------------------ */
/*  component                                                          */
/* ------------------------------------------------------------------ */

export function AdminPayrollApprovalsPage() {
  const [items, setItems] = useState<PayrollRuleVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogAction, setDialogAction] = useState<"APPROVE" | "REJECT">("APPROVE");
  const [dialogItem, setDialogItem] = useState<PayrollRuleVersion | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await listPayrollApprovals();
      setItems(result.items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchItems();
  }, [fetchItems]);

  function openDialog(item: PayrollRuleVersion, action: "APPROVE" | "REJECT") {
    setDialogItem(item);
    setDialogAction(action);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setDialogItem(null);
  }

  async function handleConfirm(_reason: string) {
    if (!dialogItem) return;
    try {
      await decidePayrollRule(dialogItem.rule_version_id, dialogAction === "APPROVE");
      void fetchItems();
      closeDialog();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "审核失败");
      closeDialog();
    }
  }

  const dialogPreCheck = useMemo(
    () => (dialogItem ? buildPreCheck(dialogItem) : undefined),
    [dialogItem],
  );

  const dialogImpact = useMemo((): ImpactScope | undefined => {
    if (!dialogItem) return undefined;
    return {
      factories: [dialogItem.factory_id],
      affectedRecords: 120,
    };
  }, [dialogItem]);

  if (loading) return <div role="status" className="page-loading">正在加载工资规则审批列表...</div>;
  if (error && items.length === 0) return <div role="alert" className="error-banner">{error}</div>;

  return (
    <section className="payroll-page" data-testid="finance-payroll-rules-page">
      <header><h1 data-testid="finance-page-title">工资规则审批</h1><p>批准后规则才具备唯一执行资格。查看规则版本差异与试算样本对比。</p></header>

      {error && <div role="alert" className="error-banner">{error}</div>}

      {items.length === 0 ? (
        <p className="vex-empty">当前没有待审批工资规则。</p>
      ) : (
        <div className="payroll-list">
          {items.map((item) => {
            const preCheck = buildPreCheck(item);
            const samples = buildTrialSamples(item);
            return (
              <article key={item.rule_version_id} className="payroll-card-enhanced">
                <div className="payroll-card-header">
                  <strong>{item.name} V{item.version}</strong>
                  <span>{item.factory_id} · {item.dsl.metric} x {item.dsl.rate} + {item.dsl.base}</span>
                </div>

                {/* rule version diff */}
                <VersionDiffPanel
                  title="规则版本差异"
                  ruleLines={buildRuleDiff(item)}
                  emptyMessage="无上一版本可对比。"
                />

                {/* pre-check */}
                <div className={`precheck-summary ${preCheck.passed ? "precheck-passed" : "precheck-failed"}`}>
                  <strong>预检结果：{preCheck.passed ? "通过" : "未通过"}</strong>
                  {preCheck.errors.length > 0 && (
                    <ul>{preCheck.errors.map((e, i) => <li key={`e-${i}`}>{e}</li>)}</ul>
                  )}
                  {preCheck.warnings.length > 0 && (
                    <ul>{preCheck.warnings.map((w, i) => <li key={`w-${i}`}>{w}</li>)}</ul>
                  )}
                </div>

                {/* trial samples */}
                <div className="trial-samples">
                  <h4>试算样本对比</h4>
                  <table className="trial-table">
                    <thead>
                      <tr>
                        <th>员工</th>
                        <th>指标值</th>
                        <th>原金额</th>
                        <th>新金额</th>
                        <th>差额</th>
                      </tr>
                    </thead>
                    <tbody>
                      {samples.map((s) => (
                        <tr key={s.employee_code}>
                          <td>{s.employee_code}</td>
                          <td>{s.metric_value}</td>
                          <td>{s.old_amount}</td>
                          <td>{s.new_amount}</td>
                          <td className={s.delta.startsWith("+") ? "delta-positive" : "delta-negative"}>
                            {s.delta}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                <div className="managed-form-actions">
                  <button type="button" onClick={() => openDialog(item, "APPROVE")}>批准生效</button>
                  <button type="button" onClick={() => openDialog(item, "REJECT")}>退回</button>
                </div>
              </article>
            );
          })}
        </div>
      )}

      <ReasonConfirmDialog
        open={dialogOpen}
        title={dialogAction === "APPROVE" ? "批准工资规则" : "退回工资规则"}
        action={dialogAction}
        preCheck={dialogPreCheck}
        impactScope={dialogImpact}
        onConfirm={handleConfirm}
        onCancel={closeDialog}
      />
    </section>
  );
}
