import { useCallback, useEffect, useMemo, useState } from "react";

import { adminTrialPayroll, decidePayrollRule, listPayrollApprovals } from "./api";
import type { TrialPayrollResult } from "./api";
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

function buildPreCheck(item: PayrollRuleVersion, trialData?: TrialPayrollResult | null): PreCheckResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!item.dsl.metric) {
    errors.push("计算指标 (metric) 未指定");
  }
  const rate = parseFloat(item.dsl.rate);
  if (item.dsl.rate && (isNaN(rate) || rate <= 0)) {
    errors.push("单价 (rate) 无效或非正数");
  }
  if (trialData && trialData.result_count === 0) {
    warnings.push("当前没有可计算正式记录");
  }

  return { passed: errors.length === 0, errors, warnings };
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

  /* trial calculation state per item */
  const [trialLoading, setTrialLoading] = useState<Record<string, boolean>>({});
  const [trialData, setTrialData] = useState<Record<string, TrialPayrollResult | null>>({});
  const [trialError, setTrialError] = useState<Record<string, string>>({});

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

  async function handleTrial(item: PayrollRuleVersion) {
    const id = item.rule_version_id;
    setTrialLoading((prev) => ({ ...prev, [id]: true }));
    setTrialError((prev) => ({ ...prev, [id]: "" }));
    try {
      const result = await adminTrialPayroll(id, "2026-01-01", "2026-12-31");
      setTrialData((prev) => ({ ...prev, [id]: result }));
    } catch (cause) {
      setTrialError((prev) => ({ ...prev, [id]: cause instanceof Error ? cause.message : "试算失败" }));
    } finally {
      setTrialLoading((prev) => ({ ...prev, [id]: false }));
    }
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
    () => (dialogItem ? buildPreCheck(dialogItem, trialData[dialogItem.rule_version_id]) : undefined),
    [dialogItem, trialData],
  );

  const dialogImpact = useMemo((): ImpactScope | undefined => {
    if (!dialogItem) return undefined;
    const td = trialData[dialogItem.rule_version_id];
    return {
      factories: [dialogItem.factory_id],
      affectedRecords: td ? td.result_count : 0,
    };
  }, [dialogItem, trialData]);

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
            const itemId = item.rule_version_id;
            const td = trialData[itemId];
            const tl = trialLoading[itemId];
            const te = trialError[itemId];
            const preCheck = buildPreCheck(item, td);
            return (
              <article key={itemId} className="payroll-card-enhanced">
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

                {/* trial calculation */}
                <div className="trial-samples">
                  <h4>试算结果</h4>
                  {!td && !tl && !te && (
                    <button type="button" className="trial-run-btn" onClick={() => { void handleTrial(item); }}>
                      执行试算
                    </button>
                  )}
                  {tl && <p className="trial-loading">正在试算...</p>}
                  {te && <p className="trial-error">{te}</p>}
                  {td && (
                    <>
                      <p className="trial-summary">
                        共 {td.result_count} 条记录，涉及 {td.items.length} 名员工
                      </p>
                      {td.items.length > 0 && (
                        <table className="trial-table">
                          <thead>
                            <tr>
                              <th>员工</th>
                              <th>日期</th>
                              <th>金额</th>
                              <th>原金额</th>
                              <th>差额</th>
                            </tr>
                          </thead>
                          <tbody>
                            {td.items.slice(0, 5).map((s, i) => (
                              <tr key={`${s.employee_code}-${i}`}>
                                <td>{s.employee_code}</td>
                                <td>{s.business_date}</td>
                                <td>{s.amount}</td>
                                <td>{s.original_amount ?? "-"}</td>
                                <td className={(s.delta_amount && s.delta_amount.startsWith("-")) ? "delta-negative" : "delta-positive"}>
                                  {s.delta_amount ?? "-"}
                                </td>
                              </tr>
                            ))}
                            {td.items.length > 5 && (
                              <tr><td colSpan={5}>... 还有 {td.items.length - 5} 条记录未完全展示</td></tr>
                            )}
                          </tbody>
                        </table>
                      )}
                      <button type="button" className="trial-run-btn" onClick={() => { void handleTrial(item); }}>
                        重新试算
                      </button>
                    </>
                  )}
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
