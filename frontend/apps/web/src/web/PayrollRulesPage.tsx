import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import {
  calculatePayroll,
  confirmPayrollBatch,
  createPayrollRule,
  listFinanceCorrections,
  listOfficialPayroll,
  listPayrollBatches,
  listPayrollRules,
  submitPayrollRule,
  trialCalculatePayroll,
} from "./api";
import type { TrialPayrollResult } from "./api";
import type { PayrollBatch, PayrollResult, PayrollRuleVersion, SubmissionCorrection } from "./types";
import { DetailDrawer, DetailField, StatusBadge, ReasonConfirmDialog } from "./shared";
import type { PreCheckResult } from "./shared";
import "./finance-pages.css";
import "./payroll-pages.css";

interface PreCheckItem {
  label: string;
  pass: boolean | null;
}

const AVAILABLE_METRICS: { value: string; label: string }[] = [
  { value: "qualified_quantity", label: "合格数量 (qualified_quantity)" },
  { value: "total_quantity", label: "总数量 (total_quantity)" },
  { value: "defect_quantity", label: "次品数量 (defect_quantity)" },
  { value: "work_hours", label: "工时 (work_hours)" },
  { value: "overtime_hours", label: "加班工时 (overtime_hours)" },
];

export function PayrollRulesPage() {
  const [rules, setRules] = useState<PayrollRuleVersion[]>([]);
  const [batches, setBatches] = useState<PayrollBatch[]>([]);
  const [results, setResults] = useState<PayrollResult[]>([]);
  const [corrections, setCorrections] = useState<SubmissionCorrection[]>([]);
  const [error, setError] = useState("");

  // Trial state
  const [trialRule, setTrialRule] = useState<PayrollRuleVersion | null>(null);
  const [trialResults, setTrialResults] = useState<TrialPayrollResult | null>(null);
  const [trialLoading, setTrialLoading] = useState(false);
  const [trialOpen, setTrialOpen] = useState(false);

  // Submit approval dialog
  const [approvalRule, setApprovalRule] = useState<PayrollRuleVersion | null>(null);
  const [approvalOpen, setApprovalOpen] = useState(false);

  // Batch confirmation dialog
  const [batchConfirmOpen, setBatchConfirmOpen] = useState(false);
  const [batchToConfirm, setBatchToConfirm] = useState<PayrollBatch | null>(null);

  function reload() {
    void Promise.all([
      listPayrollRules(),
      listPayrollBatches(),
      listOfficialPayroll("finance"),
      listFinanceCorrections(),
    ])
      .then(([ruleData, batchData, resultData, correctionData]) => {
        setRules(ruleData.items);
        setBatches(batchData.items);
        setResults(resultData.items);
        setCorrections(correctionData.items);
      })
      .catch((cause: unknown) =>
        setError(cause instanceof Error ? cause.message : "工资数据加载失败"),
      );
  }
  useEffect(reload, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    try {
      await createPayrollRule({
        rule_key: String(data.get("rule_key")),
        name: String(data.get("name")),
        factory_id: String(data.get("factory_id")),
        position: "WORKER",
        dsl: {
          metric: String(data.get("metric")),
          rate: String(data.get("rate")),
          base: String(data.get("base") || "0"),
        },
      });
      event.currentTarget.reset();
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "规则保存失败");
    }
  }

  async function calculate(rule: PayrollRuleVersion) {
    const today = new Date().toISOString().slice(0, 10);
    try {
      await calculatePayroll(rule.rule_version_id, `${today.slice(0, 7)}-01`, today);
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "计算失败");
    }
  }

  function openTrial(rule: PayrollRuleVersion) {
    setTrialRule(rule);
    setTrialResults(null);
    setTrialLoading(true);
    setTrialOpen(true);
    const today = new Date().toISOString().slice(0, 10);
    trialCalculatePayroll(rule.rule_version_id, `${today.slice(0, 7)}-01`, today)
      .then((result) => {
        setTrialResults(result);
        setTrialLoading(false);
      })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "试算失败");
        setTrialLoading(false);
      });
  }

  function openApproval(rule: PayrollRuleVersion) {
    setApprovalRule(rule);
    setApprovalOpen(true);
  }

  async function handleSubmitApproval(_reason: string) {
    if (!approvalRule) return;
    try {
      await submitPayrollRule(approvalRule.rule_version_id);
      setApprovalOpen(false);
      setApprovalRule(null);
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "提交审批失败");
    }
  }

  function openBatchConfirm(batch: PayrollBatch) {
    setBatchToConfirm(batch);
    setBatchConfirmOpen(true);
  }

  async function handleBatchConfirm(_reason: string) {
    if (!batchToConfirm) return;
    try {
      await confirmPayrollBatch(batchToConfirm.batch_id);
      setBatchConfirmOpen(false);
      setBatchToConfirm(null);
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "批次确认失败");
    }
  }

  // Pre-check for rule submission approval (§8.8.2)
  const approvalPreCheck = useMemo<PreCheckResult>(() => {
    const items: PreCheckItem[] = [];

    // 1. Required exceptions resolved
    const unresolved = corrections.filter(
      (c) => c.status !== "RESOLVED" && c.status !== "APPROVED",
    );
    items.push({
      label: "必需异常已解决",
      pass: unresolved.length === 0,
    });

    // 2. Rule version valid
    items.push({
      label: "规则版本有效",
      pass: approvalRule
        ? approvalRule.status === "APPROVED" || approvalRule.status === "DRAFT"
        : false,
    });

    // 3. Source facts validated server-side on submission
    items.push({
      label: "来源事实有效 — 提交时由服务器验证",
      pass: null,
    });

    // 4. Trial/official calculation completed
    const hasCalc = results.length > 0 ||
      batches.some((b) => b.rule_version_id === approvalRule?.rule_version_id && b.status !== "PENDING");
    items.push({
      label: "试算/正式计算已完成",
      pass: hasCalc || approvalRule?.status === "DRAFT",
    });

    // 5. Current revision expiry checked server-side on submission
    items.push({
      label: "当前 revision 未过期 — 提交时由服务器验证",
      pass: null,
    });

    // 6. Permission checked server-side on submission
    items.push({
      label: "当前用户有财务确认权限 — 提交时由服务器验证",
      pass: null,
    });

    const allPassed = items.filter((c) => c.pass !== null).every((c) => c.pass);
    return {
      passed: allPassed,
      errors: items.filter((c) => c.pass === false).map((c) => c.label),
      warnings: allPassed
        ? ["提交后将进入管理员审批流程", "审批通过后才可正式执行计算"]
        : ["请先解决以上未通过项再提交审批"],
    };
  }, [approvalRule, corrections, results, batches]);

  // Pre-check items rendered as list for the approval dialog
  const approvalPreCheckItems = useMemo<PreCheckItem[]>(() => {
    const items: PreCheckItem[] = [];
    const unresolved = corrections.filter(
      (c) => c.status !== "RESOLVED" && c.status !== "APPROVED",
    );
    items.push({ label: "必需异常已解决", pass: unresolved.length === 0 });
    items.push({
      label: "规则版本有效",
      pass: approvalRule
        ? approvalRule.status === "APPROVED" || approvalRule.status === "DRAFT"
        : false,
    });
    items.push({ label: "来源事实有效 — 提交时由服务器验证", pass: null });
    const hasCalc = results.length > 0 ||
      batches.some((b) => b.rule_version_id === approvalRule?.rule_version_id && b.status !== "PENDING");
    items.push({ label: "试算/正式计算已完成", pass: hasCalc || approvalRule?.status === "DRAFT" });
    items.push({ label: "当前 revision 未过期 — 提交时由服务器验证", pass: null });
    items.push({ label: "当前用户有财务确认权限 — 提交时由服务器验证", pass: null });
    return items;
  }, [approvalRule, corrections, results, batches]);

  // Batch confirmation pre-check
  const batchPreCheck = useMemo<PreCheckResult>(() => {
    if (!batchToConfirm) return { passed: false, errors: ["未选择批次"], warnings: [] };
    const items: PreCheckItem[] = [];
    const unresolved = corrections.filter(
      (c) => c.status !== "RESOLVED" && c.status !== "APPROVED",
    );
    items.push({ label: "必需异常已解决", pass: unresolved.length === 0 });
    items.push({
      label: "规则版本有效",
      pass: rules.some(
        (r) => r.rule_version_id === batchToConfirm.rule_version_id && r.status === "APPROVED",
      ),
    });
    items.push({ label: "来源事实有效 — 提交时由服务器验证", pass: null });
    items.push({ label: "试算/正式计算已完成", pass: batchToConfirm.status !== "PENDING" });
    items.push({ label: "当前 revision 未过期 — 提交时由服务器验证", pass: null });
    items.push({ label: "当前用户有财务确认权限 — 提交时由服务器验证", pass: null });

    const allPassed = items.filter((c) => c.pass !== null).every((c) => c.pass);
    const ruleForBatch = rules.find((r) => r.rule_version_id === batchToConfirm.rule_version_id);
    return {
      passed: allPassed,
      errors: items.filter((c) => c.pass === false).map((c) => c.label),
      warnings: allPassed
        ? [
            `确认后将锁定批次，工厂 ${batchToConfirm.factory_id}`,
            `员工数 ${results.length}，总金额 ${results.reduce((s, r) => s + Number(r.amount || 0), 0).toFixed(2)}`,
            `规则版本 ${ruleForBatch ? `${ruleForBatch.name} V${ruleForBatch.version}` : batchToConfirm.rule_version_id}`,
            "确认后不可撤回，正式工资将进入财务账本。",
          ]
        : ["请先解决以上未通过项再确认"],
    };
  }, [batchToConfirm, corrections, rules, results]);

  // Batch pre-check items for rendering
  const batchPreCheckItems = useMemo<PreCheckItem[]>(() => {
    if (!batchToConfirm) return [];
    const items: PreCheckItem[] = [];
    const unresolved = corrections.filter(
      (c) => c.status !== "RESOLVED" && c.status !== "APPROVED",
    );
    items.push({ label: "必需异常已解决", pass: unresolved.length === 0 });
    items.push({
      label: "规则版本有效",
      pass: rules.some(
        (r) => r.rule_version_id === batchToConfirm.rule_version_id && r.status === "APPROVED",
      ),
    });
    items.push({ label: "来源事实有效 — 提交时由服务器验证", pass: null });
    items.push({ label: "试算/正式计算已完成", pass: batchToConfirm.status !== "PENDING" });
    items.push({ label: "当前 revision 未过期 — 提交时由服务器验证", pass: null });
    items.push({ label: "当前用户有财务确认权限 — 提交时由服务器验证", pass: null });
    return items;
  }, [batchToConfirm, corrections, rules]);

  return (
    <section className="payroll-page">
      <header>
        <h1>工资规则与计算</h1>
        <p>规则经管理员批准后才可执行；每个结果固定绑定规则版本和数据水位。</p>
      </header>
      {error && <div role="alert" className="error-banner">{error}</div>}

      {/* Create form (preserved) */}
      <form className="payroll-rule-form" onSubmit={create}>
        <label>规则名称<input name="name" required /></label>
        <label>规则标识<input name="rule_key" required /></label>
        <label>工厂<input name="factory_id" required /></label>
        <label>计量字段
          <select name="metric" required>
            <option value="">-- 选择计量字段 --</option>
            {AVAILABLE_METRICS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </label>
        <label>单价<input name="rate" inputMode="decimal" required /></label>
        <label>基础金额<input name="base" inputMode="decimal" defaultValue="0" /></label>
        <button type="submit">保存工资规则草稿</button>
      </form>

      {/* Enhanced rules list */}
      <h2>规则版本</h2>
      <div className="payroll-list">
        {rules.map((rule) => (
          <div key={rule.rule_version_id} className="finance-payroll-rule-item">
            <div className="finance-payroll-rule-info">
              <strong>{rule.name} V{rule.version}</strong>
              <span>{rule.factory_id} · {rule.position} · {rule.dsl.metric} x {rule.dsl.rate}</span>
              <span>生效日期: — · 最近试算: —</span>
            </div>
            <StatusBadge status={rule.status} />
            <div className="finance-payroll-rule-actions">
              {rule.status === "DRAFT" && (
                <button type="button" className="primary" onClick={() => openApproval(rule)}>
                  提交审批
                </button>
              )}
              {rule.status === "APPROVED" && (
                <>
                  <button type="button" className="primary" onClick={() => void calculate(rule)}>
                    按本月计算
                  </button>
                  <button type="button" onClick={() => openTrial(rule)}>
                    试算对比
                  </button>
                </>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Batches */}
      <h2>计算批次</h2>
      <div className="payroll-list">
        {batches.map((batch) => (
          <article key={batch.batch_id}>
            <strong>{batch.batch_type} · {batch.status}</strong>
            <span>{batch.period_start} 至 {batch.period_end}</span>
            {batch.status === "PENDING_FINANCE" && (
              <button type="button" onClick={() => openBatchConfirm(batch)}>
                财务确认
              </button>
            )}
          </article>
        ))}
      </div>

      {/* Official payroll (preserved) */}
      <h2>正式工资</h2>
      <div className="payroll-list">
        {results.map((result) => (
          <article key={result.result_id}>
            <strong>{result.employee_code}</strong>
            <span>¥ {result.amount}</span>
          </article>
        ))}
      </div>

      {/* Trial Panel Drawer */}
      <DetailDrawer
        open={trialOpen}
        onClose={() => setTrialOpen(false)}
        title={`试算面板 — ${trialRule?.name ?? ""} V${trialRule?.version ?? ""}`}
      >
        <div className="finance-payroll-trial-panel">
          <h3>实时试算结果</h3>
          {trialLoading && <p>正在从后端计算试算结果…</p>}
          {!trialLoading && trialResults === null && (
            <p>无法加载试算数据。</p>
          )}
          {!trialLoading && trialResults && trialResults.items.length === 0 && (
            <p>当前周期内无适用记录。</p>
          )}
          {!trialLoading && trialResults && trialResults.items.length > 0 && (
            <>
              <p style={{ fontSize: 13, color: "#596579" }}>
                共 {trialResults.result_count} 条记录（干跑模式，未创建持久批次）
              </p>
              <table className="finance-trial-table">
                <thead>
                  <tr>
                    <th>员工</th>
                    <th>旧规则金额</th>
                    <th>新规则金额</th>
                    <th>差额</th>
                    <th>结果</th>
                  </tr>
                </thead>
                <tbody>
                  {trialResults.items.map((r, idx) => {
                    const oldAmt = Number(r.original_amount ?? 0);
                    const newAmt = Number(r.amount);
                    const delta = newAmt - oldAmt;
                    return (
                      <tr key={`${r.employee_code}-${idx}`}>
                        <td>{r.employee_code}</td>
                        <td className="amount">{oldAmt.toFixed(2)}</td>
                        <td className="amount">{newAmt.toFixed(2)}</td>
                        <td className={`amount ${delta >= 0 ? "delta-positive" : "delta-negative"}`}>
                          {delta >= 0 ? "+" : ""}{delta.toFixed(2)}
                        </td>
                        <td>{delta === 0 ? "无变化" : "有差异"}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </>
          )}
          {trialRule && (
            <DetailField label="规则" value={`${trialRule.name} V${trialRule.version}`} />
          )}
          <DetailField label="工厂" value={trialRule?.factory_id ?? "—"} />
          <DetailField label="公式" value={trialRule ? `${trialRule.dsl.metric} x ${trialRule.dsl.rate} + ${trialRule.dsl.base}` : "—"} />
        </div>
      </DetailDrawer>

      {/* Submit Approval Dialog with pre-check items (§8.8.2) */}
      {approvalOpen && approvalRule && (
        <div className="dialog-overlay" role="dialog" aria-modal="true" aria-label={`提交审批 — ${approvalRule.name}`}>
          <div className="dialog-content" style={{ maxWidth: 520 }}>
            <h2>提交审批 — {approvalRule.name} V{approvalRule.version}</h2>

            {/* Summary info */}
            <div className="finance-correction-info">
              <p><strong>工厂：</strong>{approvalRule.factory_id} · <strong>岗位：</strong>{approvalRule.position}</p>
              <p><strong>规则：</strong>{approvalRule.dsl.metric} x {approvalRule.dsl.rate} + {approvalRule.dsl.base}</p>
            </div>

            {/* Pre-check checklist */}
            <div className="finance-precheck-list">
              <h3>确认前检查</h3>
              {approvalPreCheckItems.map((item) => (
                <div
                  key={item.label}
                  className={`finance-precheck-item ${item.pass === true ? "finance-precheck-item--pass" : item.pass === false ? "finance-precheck-item--fail" : "finance-precheck-item--neutral"}`}
                >
                  <span className={`finance-precheck-icon`}>
                    {item.pass === true ? "✅" : item.pass === false ? "❌" : "—"}
                  </span>
                  <span className="finance-precheck-label">{item.label}</span>
                </div>
              ))}
            </div>

            {/* Warnings */}
            {approvalPreCheck.warnings.length > 0 && (
              <div className="dialog-precheck">
                <ul className="precheck-warnings">
                  {approvalPreCheck.warnings.map((w, i) => (
                    <li key={i} className="precheck-warning-item">{w}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="dialog-actions">
              <button
                type="button"
                className="dialog-btn-cancel"
                onClick={() => { setApprovalOpen(false); setApprovalRule(null); }}
              >
                取消
              </button>
              <button
                type="button"
                className="dialog-btn-confirm"
                style={{ background: "#155eef" }}
                disabled={!approvalPreCheck.passed}
                onClick={() => void handleSubmitApproval("提交审批")}
              >
                确认提交审批
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Batch Confirm Dialog with pre-check items (§8.8.2) */}
      {batchConfirmOpen && batchToConfirm && (
        <div className="dialog-overlay" role="dialog" aria-modal="true" aria-label={`确认批次 — ${batchToConfirm.batch_id}`}>
          <div className="dialog-content" style={{ maxWidth: 520 }}>
            <h2>财务确认工资批次</h2>

            {/* Summary info */}
            <div className="finance-correction-info">
              <p><strong>批次：</strong>{batchToConfirm.batch_id}</p>
              <p><strong>工厂：</strong>{batchToConfirm.factory_id} · <strong>范围：</strong>{batchToConfirm.period_start} 至 {batchToConfirm.period_end}</p>
              <p><strong>类型：</strong>{batchToConfirm.batch_type} · <strong>状态：</strong>{batchToConfirm.status}</p>
            </div>

            {/* Pre-check checklist */}
            <div className="finance-precheck-list">
              <h3>确认前检查</h3>
              {batchPreCheckItems.map((item) => (
                <div
                  key={item.label}
                  className={`finance-precheck-item ${item.pass === true ? "finance-precheck-item--pass" : item.pass === false ? "finance-precheck-item--fail" : "finance-precheck-item--neutral"}`}
                >
                  <span className="finance-precheck-icon">
                    {item.pass === true ? "✅" : item.pass === false ? "❌" : "—"}
                  </span>
                  <span className="finance-precheck-label">{item.label}</span>
                </div>
              ))}
            </div>

            {/* Consequences */}
            {batchPreCheck.warnings.length > 0 && (
              <div className="dialog-precheck">
                <ul className="precheck-warnings">
                  {batchPreCheck.warnings.map((w, i) => (
                    <li key={i} className="precheck-warning-item">{w}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="dialog-actions">
              <button
                type="button"
                className="dialog-btn-cancel"
                onClick={() => { setBatchConfirmOpen(false); setBatchToConfirm(null); }}
              >
                取消
              </button>
              <button
                type="button"
                className="dialog-btn-confirm"
                style={{ background: batchPreCheck.passed ? "#155eef" : "#9d2424" }}
                disabled={!batchPreCheck.passed}
                onClick={() => void handleBatchConfirm("财务确认")}
              >
                确认
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Keep existing ReasonConfirmDialog for compatibility */}
      <ReasonConfirmDialog
        open={false}
        title=""
        action="APPROVE"
        preCheck={{ passed: true, errors: [], warnings: [] }}
        onConfirm={() => {}}
        onCancel={() => {}}
      />
    </section>
  );
}
