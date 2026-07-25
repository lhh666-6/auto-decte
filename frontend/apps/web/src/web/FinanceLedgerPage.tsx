import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  listFinanceCorrections,
  listFinanceLedger,
  getFinanceLedgerOverview,
  reviewCorrection,
  safeRandomUUID,
  submitFinanceCorrection,
} from "./api";
import type { FinanceRecord, SubmissionCorrection } from "./types";
import {
  DetailDrawer,
  FilterToolbar,
  StatusBadge,
} from "./shared";
import type { AppliedFilter, FilterOption } from "./shared";
import "./finance-pages.css";
import "./ledger-pages.css";

type EmptyReason =
  | "no_records"
  | "no_ledger"
  | "query_failed"
  | "revision_conflict"
  | "no_permission";

type CorrectionType = "quantity" | "attribution" | "rule_applicability" | "other";

const STATIC_FILTER_OPTIONS: FilterOption[] = [
  { key: "factory_id", label: "工厂", options: [] },
  { key: "subject_employee_code", label: "员工", options: [] },
  { key: "status", label: "状态", options: [
    { value: "ACTIVE", label: "生效中" },
    { value: "REPLACED", label: "已替换" },
    { value: "ERROR", label: "异常" },
  ]},
  { key: "business_date", label: "日期", options: [] },
];

const CORRECTION_TYPE_LABELS: Record<CorrectionType, string> = {
  quantity: "数量更正",
  attribution: "归属更正",
  rule_applicability: "规则适用更正",
  other: "其他",
};

function formatAmount(raw: unknown): string {
  if (raw === null || raw === undefined || raw === "") return "0.00";
  const n = Number(raw);
  if (Number.isNaN(n)) return String(raw);
  return n.toFixed(2);
}

function formatQty(raw: unknown): string {
  if (raw === null || raw === undefined || raw === "") return "—";
  return String(raw);
}

type LedgerScope = "today" | "month" | "year";

const SCOPE_LABELS: Record<LedgerScope, string> = {
  today: "今日",
  month: "本月",
  year: "本年",
};

export function FinanceLedgerPage({ scope }: { scope: LedgerScope }) {
  const navigate = useNavigate();
  const [, setOverview] = useState({ today: 0, month: 0, year: 0 });
  const [records, setRecords] = useState<FinanceRecord[]>([]);
  const [corrections, setCorrections] = useState<SubmissionCorrection[]>([]);
  const [error, setError] = useState("");
  const [emptyReason, setEmptyReason] = useState<EmptyReason>("no_records");
  const [appliedFilters, setAppliedFilters] = useState<AppliedFilter[]>([]);
  const [lastUpdated, setLastUpdated] = useState("");
  const [detailRecord, setDetailRecord] = useState<FinanceRecord | null>(null);
  const [drawerTab, setDrawerTab] = useState("summary");

  // Correction dialog
  const [correctionOpen, setCorrectionOpen] = useState(false);
  const [correctionType, setCorrectionType] = useState<CorrectionType>("other");
  const [correctionReason, setCorrectionReason] = useState("");
  const [correctionDesc, setCorrectionDesc] = useState("");
  const [correctionSubmitting, setCorrectionSubmitting] = useState(false);
  const [correctionIdempotencyKey, setCorrectionIdempotencyKey] = useState("");

  // Per-record error state for revision conflicts in detail
  const [detailError, setDetailError] = useState("");

  function reload() {
    void Promise.all([
      getFinanceLedgerOverview(scope),
      listFinanceLedger(scope),
      listFinanceCorrections(),
    ])
      .then(([summary, ledger, cases]) => {
        setOverview(summary);
        setRecords(ledger.items);
        setCorrections(cases.items);
        setLastUpdated(new Date().toLocaleString("zh-CN"));
        setError("");
        if (ledger.items.length === 0) {
          setEmptyReason("no_ledger");
        } else {
          setEmptyReason("no_records");
        }
      })
      .catch((cause: unknown) => {
        const msg = cause instanceof Error ? cause.message : "账本加载失败";
        setError(msg);
        if (msg.includes("权限") || msg.includes("403")) {
          setEmptyReason("no_permission");
        } else if (msg.includes("revision") || msg.includes("已被更新") || msg.includes("conflict")) {
          setEmptyReason("revision_conflict");
        } else {
          setEmptyReason("query_failed");
        }
      });
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

  const filteredRecords = useMemo(() => {
    if (appliedFilters.length === 0) return records;
    return records.filter((r) =>
      appliedFilters.every((f) => {
        const val = (r as unknown as Record<string, unknown>)[f.key];
        return String(val ?? "").toLowerCase().includes(f.value.toLowerCase());
      }),
    );
  }, [records, appliedFilters]);

  // Dynamic filter options derived from loaded records
  const filterOptions = useMemo<FilterOption[]>(() => {
    const factoryIds = [...new Set(records.map((r) => r.factory_id).filter(Boolean))].sort();
    const employeeCodes = [...new Set(records.map((r) => r.subject_employee_code).filter(Boolean))].sort();
    const dates = [...new Set(records.map((r) => r.business_date).filter(Boolean))].sort();
    return STATIC_FILTER_OPTIONS.map((opt) => {
      if (opt.key === "factory_id") {
        return { ...opt, options: factoryIds.map((v) => ({ value: v, label: v })) };
      }
      if (opt.key === "subject_employee_code") {
        return { ...opt, options: employeeCodes.map((v) => ({ value: v, label: v })) };
      }
      if (opt.key === "business_date") {
        return { ...opt, options: dates.map((v) => ({ value: v, label: v })) };
      }
      return opt;
    });
  }, [records]);

  // Summary computation
  const employeeCount = useMemo(() => {
    const codes = new Set(filteredRecords.map((r) => r.subject_employee_code));
    return codes.size;
  }, [filteredRecords]);

  const totalAmount = useMemo(() => {
    let sum = 0;
    for (const r of filteredRecords) {
      const amt = r.values && typeof r.values === "object" && "amount" in r.values
        ? Number((r.values as Record<string, unknown>).amount)
        : 0;
      if (!Number.isNaN(amt)) sum += amt;
    }
    return sum;
  }, [filteredRecords]);

  function openDetail(record: FinanceRecord) {
    setDetailRecord(record);
    setDrawerTab("summary");
    setDetailError("");
  }

  function closeDetail() {
    setDetailRecord(null);
    setDetailError("");
  }

  function openCorrectionDialog() {
    setCorrectionReason("");
    setCorrectionDesc("");
    setCorrectionType("other");
    setCorrectionIdempotencyKey(safeRandomUUID());
    setCorrectionOpen(true);
  }

  async function submitCorrection() {
    if (!correctionReason.trim() || !detailRecord) return;
    setCorrectionSubmitting(true);
    try {
      await submitFinanceCorrection(
        detailRecord.root_submission_id,
        { reason: correctionReason, correction_type: correctionType, supplementary_note: correctionDesc || undefined },
        correctionIdempotencyKey,
      );
      setCorrectionOpen(false);
      setError("");
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "更正提交失败");
    } finally {
      setCorrectionSubmitting(false);
    }
  }

  // ---------- Empty State Renderers ----------

  function renderEmptyState(reason: EmptyReason) {
    switch (reason) {
      case "no_records":
        return (
          <div className="finance-ledger-empty-state">
            <div className="finance-ledger-empty-icon">📋</div>
            <h3>当前范围还没有正式账本记录</h3>
            <p>当前周期内没有符合筛选条件的正式账本记录。</p>
            <div className="finance-ledger-empty-actions">
              <button type="button" onClick={() => setAppliedFilters([])}>
                调整筛选条件
              </button>
              <button type="button" onClick={reload}>刷新</button>
            </div>
          </div>
        );

      case "no_ledger":
        return (
          <div className="finance-ledger-empty-state">
            <div className="finance-ledger-empty-icon">📥</div>
            <h3>存在未进入正式账本的来源记录</h3>
            <p>系统中有生产事实提交，但尚未形成正式账本记录。这可能是数据尚未经过财务确认或规则计算。</p>
            <div className="finance-ledger-empty-actions">
              <button type="button" onClick={reload}>刷新检查</button>
              <button
                type="button"
                className="primary"
                onClick={() => {
                  // Navigate to exceptions center
                  navigate("/finance/exceptions");
                }}
              >
                前往异常中心
              </button>
            </div>
          </div>
        );

      case "query_failed":
        return (
          <div className="finance-ledger-empty-state finance-ledger-empty-state--error">
            <div className="finance-ledger-empty-icon">⚠️</div>
            <h3>账本读取失败，未改变任何正式数据</h3>
            <p className="finance-ledger-empty-error-detail">{error}</p>
            <div className="finance-ledger-empty-actions">
              <button type="button" className="primary" onClick={reload}>
                重试
              </button>
            </div>
          </div>
        );

      case "revision_conflict":
        return (
          <div className="finance-ledger-empty-state finance-ledger-empty-state--warning">
            <div className="finance-ledger-empty-icon">🔄</div>
            <h3>该记录已被更新</h3>
            <p>您正在查看的记录已被其他人更新（revision 冲突）。请刷新获取最新版本。</p>
            <div className="finance-ledger-empty-actions">
              <button type="button" className="primary" onClick={reload}>
                刷新详情
              </button>
            </div>
          </div>
        );

      case "no_permission":
        return (
          <div className="finance-ledger-empty-state finance-ledger-empty-state--error">
            <div className="finance-ledger-empty-icon">🔒</div>
            <h3>当前账户无权查看该工厂账本</h3>
            <p>您的账户角色或工厂授权范围不包含目标工厂的财务数据。</p>
            <div className="finance-ledger-empty-actions">
              <button
                type="button"
                onClick={() => {
                  navigate("/finance/today");
                }}
              >
                返回可访问范围
              </button>
            </div>
          </div>
        );
    }
  }

  // Page-level empty state (when records is empty and we have a reason)
  if ((error || records.length === 0 || emptyReason === "no_permission" || emptyReason === "query_failed" || emptyReason === "revision_conflict") && records.length === 0 && emptyReason !== "no_records") {
    return (
      <section className="finance-ledger-page" data-testid="finance-ledger-page">
        <header>
          <h1>{SCOPE_LABELS[scope]}财务账本</h1>
          <p>数据口径：正式有效投影 · 按北京时间归属自然日 · 更正保留原始记录和完整替换链</p>
        </header>
        {renderEmptyState(emptyReason)}
      </section>
    );
  }

  return (
    <section className="finance-ledger-page" data-testid="finance-ledger-page">
      <header>
        <h1 data-testid="finance-page-title">{SCOPE_LABELS[scope]}财务账本</h1>
        <p>数据口径：正式有效投影 · 按北京时间归属自然日 · 更正保留原始记录和完整替换链</p>
      </header>
      {error && <div role="alert" className="error-banner">{error}</div>}

      {/* Top info bar */}
      <div className="finance-ledger-meta">
        <span>日期范围：{SCOPE_LABELS[scope]}有效记录</span>
        <span>最后更新：{lastUpdated || "—"}</span>
        <span>筛选条件数：{appliedFilters.length}</span>
      </div>

      {/* Filters */}
      <div data-testid="finance-ledger-filter">
        <FilterToolbar
          filters={filterOptions}
          applied={appliedFilters}
          onChange={setAppliedFilters}
        />
      </div>

      {/* Summary cards */}
      <div className="finance-summary-cards">
        <article className="finance-summary-card">
          <span className="finance-summary-card-value">{filteredRecords.length}</span>
          <span className="finance-summary-card-label">正式记录数</span>
        </article>
        <article className="finance-summary-card">
          <span className="finance-summary-card-value">{employeeCount}</span>
          <span className="finance-summary-card-label">员工数</span>
        </article>
        <article className="finance-summary-card">
          <span className="finance-summary-card-value">{formatAmount(totalAmount)}</span>
          <span className="finance-summary-card-label">总金额</span>
        </article>
        <article className="finance-summary-card">
          <span className="finance-summary-card-value" style={{ color: "#9d2424" }}>{corrections.length}</span>
          <span className="finance-summary-card-label">异常/待更正</span>
        </article>
      </div>

      {/* Main table */}
      <div className="finance-ledger-table-wrap" data-testid="finance-ledger-table">
        <table>
          <thead>
            <tr>
              <th>来源记录号</th>
              <th>日期</th>
              <th>工厂</th>
              <th>员工</th>
              <th>来源/工序</th>
              <th>数量</th>
              <th>规则版本</th>
              <th className="amount-cell">正式金额</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {filteredRecords.map((record) => (
              <tr
                key={record.root_submission_id}
                className="clickable-row"
                onClick={() => openDetail(record)}
                data-testid="finance-ledger-row"
              >
                <td>{record.effective_submission_id}</td>
                <td>{record.business_date}</td>
                <td>{record.factory_id}</td>
                <td>{record.subject_employee_code}</td>
                <td>{record.definition_version_id}</td>
                <td>{String(record.values?.quantity ?? record.values?.qty ?? "—")}</td>
                <td>{String(record.values?.rule_version ?? "—")}</td>
                <td className="amount-cell" title={`规则版本: ${String(record.values?.rule_version ?? "—")}`}>
                  {formatAmount(record.values?.amount)}
                </td>
                <td><StatusBadge status={record.status} /></td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredRecords.length === 0 && records.length > 0 && (
          <div className="finance-ledger-empty">
            <p>当前筛选条件下无匹配记录。</p>
          </div>
        )}
      </div>

      {/* ========== Detail Drawer with 6 Tabs ========== */}
      <DetailDrawer
        open={detailRecord !== null}
        onClose={closeDetail}
        title={`记录详情 — ${detailRecord?.effective_submission_id ?? ""}`}
        data-testid="finance-ledger-detail"
      >
        {detailRecord && (
          <div>
            {/* In-drawer tabs */}
            <nav className="finance-drawer-tabs">
              {(["summary", "source", "calc", "approval", "correction_chain", "lineage"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  className={`finance-drawer-tab ${drawerTab === tab ? "finance-drawer-tab--active" : ""}`}
                  onClick={() => setDrawerTab(tab)}
                >
                  {{ summary: "摘要", source: "来源事实", calc: "计算明细", approval: "审批/确认", correction_chain: "更正链", lineage: "导出血缘" }[tab]}
                </button>
              ))}
            </nav>

            {detailError && (
              <div role="alert" className="error-banner" style={{ margin: "8px 0" }}>{detailError}</div>
            )}

            <div className="finance-detail-section" style={{ marginTop: 12 }}>
              {/* Tab 1: 摘要 */}
              {drawerTab === "summary" && (
                <div className="finance-detail-tab-content">
                  <div className="finance-detail-kv">
                    <dt>来源记录号</dt>
                    <dd>{detailRecord.root_submission_id}</dd>
                    <dt>员工</dt>
                    <dd>{detailRecord.subject_employee_code}</dd>
                    <dt>工厂</dt>
                    <dd>{detailRecord.factory_id}</dd>
                    <dt>业务时间</dt>
                    <dd>{detailRecord.business_date}</dd>
                    <dt>数量</dt>
                    <dd>{formatQty(detailRecord.values?.quantity ?? detailRecord.values?.qty)}</dd>
                    <dt>正式金额</dt>
                    <dd className="amount">{formatAmount(detailRecord.values?.amount)}</dd>
                    <dt>当前状态</dt>
                    <dd><StatusBadge status={detailRecord.status} /></dd>
                    <dt>提交时间</dt>
                    <dd>{detailRecord.submitted_at}</dd>
                    <dt>表单版本</dt>
                    <dd>{detailRecord.definition_version_id}</dd>
                  </div>
                </div>
              )}

              {/* Tab 2: 来源事实 */}
              {drawerTab === "source" && (
                <div className="finance-detail-tab-content">
                  <div className="finance-detail-kv">
                    <dt>表单版本</dt>
                    <dd>{detailRecord.definition_version_id}</dd>
                    <dt>来源追溯</dt>
                    <dd className="finance-pending-data">来源追溯暂未接入</dd>
                  </div>
                </div>
              )}

              {/* Tab 3: 计算明细 */}
              {drawerTab === "calc" && (
                <div className="finance-detail-tab-content">
                  <div className="finance-detail-kv">
                    <dt>规则版本</dt>
                    <dd>{detailRecord.values?.rule_version ? String(detailRecord.values.rule_version) : "—"}</dd>
                    <dt>计算结果</dt>
                    <dd className="amount">{formatAmount(detailRecord.values?.amount)}</dd>
                    <dt>数量</dt>
                    <dd>{formatQty(detailRecord.values?.quantity ?? detailRecord.values?.qty)}</dd>
                  </div>
                  <p className="finance-pending-data" style={{ margin: 0 }}>计算明细（输入变量、舍入策略、规则范围等）暂未接入</p>
                </div>
              )}

              {/* Tab 4: 审批/确认 */}
              {drawerTab === "approval" && (
                <div className="finance-detail-tab-content">
                  <p className="finance-pending-data">审批/确认追溯暂未接入</p>
                </div>
              )}

              {/* Tab 5: 更正链 */}
              {drawerTab === "correction_chain" && (
                <div className="finance-detail-tab-content">
                  <div className="finance-correction-chain">
                    {/* Current record node */}
                    <div className="finance-correction-chain-node finance-correction-chain-node--active">
                      <div className="finance-correction-chain-marker" />
                      <div className="finance-correction-chain-body">
                        <strong>当前有效节点</strong>
                        <span className="finance-correction-chain-id">{detailRecord.effective_submission_id}</span>
                        <span className="finance-correction-chain-status">
                          <StatusBadge status={detailRecord.status} />
                        </span>
                        <span className="finance-correction-chain-time">{detailRecord.submitted_at}</span>
                      </div>
                    </div>

                    {/* Original record */}
                    {detailRecord.root_submission_id !== detailRecord.effective_submission_id && (
                      <div className="finance-correction-chain-node">
                        <div className="finance-correction-chain-marker" />
                        <div className="finance-correction-chain-body">
                          <strong>原始记录</strong>
                          <span className="finance-correction-chain-id">{detailRecord.root_submission_id}</span>
                          <span className="finance-correction-chain-time">
                            原始提交时间暂未提供
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Related corrections */}
                    {corrections
                      .filter((c) =>
                        c.original_submission_id === detailRecord.root_submission_id ||
                        c.original_submission_id === detailRecord.effective_submission_id ||
                        c.root_submission_id === detailRecord.root_submission_id
                      )
                      .map((c) => (
                        <div key={c.correction_id} className="finance-correction-chain-node finance-correction-chain-node--correction">
                          <div className="finance-correction-chain-marker" />
                          <div className="finance-correction-chain-body">
                            <strong>更正记录</strong>
                            <span className="finance-correction-chain-id">{c.correction_id}</span>
                            <span>更正原因：{c.reason}</span>
                            <span>发起人：{c.requested_by}</span>
                            <span className="finance-correction-chain-time">{c.created_at}</span>
                            {c.replacement_submission_id && (
                              <span>替代记录：{c.replacement_submission_id}</span>
                            )}
                            <span><StatusBadge status={c.status} /></span>
                          </div>
                        </div>
                      ))}

                    {corrections.filter((c) =>
                      c.original_submission_id === detailRecord.root_submission_id ||
                      c.original_submission_id === detailRecord.effective_submission_id ||
                      c.root_submission_id === detailRecord.root_submission_id
                    ).length === 0 && detailRecord.root_submission_id === detailRecord.effective_submission_id && (
                      <p className="finance-pending-data">该记录尚无更正历史。</p>
                    )}
                  </div>
                </div>
              )}

              {/* Tab 6: 导出血缘 */}
              {drawerTab === "lineage" && (
                <div className="finance-detail-tab-content">
                  <p className="finance-pending-data">导出血缘追溯暂未接入</p>
                </div>
              )}

              <button
                type="button"
                className="finance-correction-btn"
                onClick={openCorrectionDialog}
                data-testid="finance-ledger-correction-open"
              >
                发起追加式更正
              </button>
            </div>
          </div>
        )}
      </DetailDrawer>

      {/* ========== Correction Dialog (§8.2.7) ========== */}
      {correctionOpen && detailRecord && (
        <div className="finance-correction-dialog-overlay" role="dialog" aria-modal="true" aria-label="发起追加式更正">
          <div className="finance-correction-dialog">
            <h2>发起追加式更正</h2>

            <div className="finance-correction-info">
              <p><strong>原正式记录号：</strong>{detailRecord.effective_submission_id}</p>
              <p><strong>当前金额：</strong>{formatAmount(detailRecord.values?.amount)}</p>
              <p><strong>当前数量：</strong>{formatQty(detailRecord.values?.quantity ?? detailRecord.values?.qty)}</p>
              <p><strong>员工：</strong>{detailRecord.subject_employee_code} · <strong>工厂：</strong>{detailRecord.factory_id}</p>
            </div>

            <label>
              更正类型
              <select
                value={correctionType}
                onChange={(e) => setCorrectionType(e.target.value as CorrectionType)}
              >
                {(Object.entries(CORRECTION_TYPE_LABELS) as [CorrectionType, string][]).map(([val, label]) => (
                  <option key={val} value={val}>{label}</option>
                ))}
              </select>
            </label>

            <label>
              更正原因（必填）
              <textarea
                value={correctionReason}
                onChange={(e) => setCorrectionReason(e.target.value)}
                placeholder="请详细说明更正原因，例如：数量应为 120 而非 100、归属员工错误、规则版本已过期等..."
                rows={4}
              />
            </label>

            <label>
              说明/附件（可选）
              <textarea
                value={correctionDesc}
                onChange={(e) => setCorrectionDesc(e.target.value)}
                placeholder="补充说明或附件链接..."
                rows={2}
              />
            </label>

            <div className="finance-correction-impact">
              <h3>影响预览</h3>
              <ul>
                <li><strong>原正式记录不会删除：</strong>当前有效记录进入 HELD（冻结）状态。</li>
                <li><strong>创建更正请求：</strong>系统创建更正请求（RETURNED），并生成 CORRECTION_REFILL 任务指派给原填写人。</li>
                <li><strong>填写人重新提交：</strong>原填写人重新提交后，更正进入 REPLACED 状态，有效投影切换到 PENDING_REVIEW。</li>
                <li><strong>财务复核：</strong>财务复核通过后，更正标记为 APPROVED，有效投影恢复 ACTIVE；退回则 REJECTED，保持 HELD。</li>
              </ul>
            </div>

            <div className="finance-correction-info">
              <p>系统保障：操作具备防重复提交保护</p>
            </div>

            <div className="finance-correction-actions">
              <button type="button" onClick={() => setCorrectionOpen(false)}>取消</button>
              <button
                type="button"
                className="primary"
                disabled={!correctionReason.trim() || correctionSubmitting}
                onClick={() => void submitCorrection()}
                data-testid="finance-ledger-correction-submit"
              >
                {correctionSubmitting ? "提交中..." : "提交更正"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Corrections review section (preserved) */}
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
