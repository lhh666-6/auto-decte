import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  auditPlantRecord,
  decidePlantInspectionAppeal,
  getPlantProductionDetail,
  safeRandomUUID,
  terminatePlantInspection,
} from "./api";
import type {
  BambooProductionDetail,
  BambooStageSubmission,
} from "./types";
import { useWebSession } from "./WebSessionProvider";
import "./plant-signature.css";

const STAGE_LABELS: Record<string, string> = {
  SORT: "分选",
  DIPPING: "浸胶",
  DRYING: "干燥",
  SUPERVISOR: "主管审核",
  PLANT_AUDIT: "厂长确认",
};

const RECORD_STATUS_LABELS: Record<string, string> = {
  ACTIVE: "进行中", COMPLETED: "已完成",
};
const CORRECTION_STATUS_LABELS: Record<string, string> = {
  SUBMITTED: "已提交", REVIEWED: "已复核", REPLACED: "已纠正",
  OVERRULED: "已驳回", CLOSED: "已关闭",
};

const FACT_TYPE_LABELS: Record<string, string> = {
  PIECE_RATE: "计件工资事实",
  QUALITY_BONUS: "质量奖金",
  PENALTY: "扣款事实",
  ATTENDANCE: "考勤事实",
};

const SIGNATURE_GATE_REASONS: Record<string, string> = {
  NOT_AT_PLANT_AUDIT: "尚未进入厂长确认环节",
  INSPECTION_IN_PROGRESS: "检测仍在进行，暂不能签字",
  APPEAL_PENDING: "检测申诉待处理，暂不能签字",
  SIGNATURE_NOT_AVAILABLE: "当前条件尚未满足",
};

function translateSignatureGateReason(raw: string): string {
  return SIGNATURE_GATE_REASONS[raw] ?? raw;
}

const STAGE_FLOW = ["SORT", "DIPPING", "DRYING", "SUPERVISOR", "PLANT_AUDIT"] as const;

function readable(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/* ---- 通用字段展示 ---- */
function Fields({ values }: { values: Record<string, unknown> }) {
  const entries = Object.entries(values);
  if (!entries.length) return <p className="signature-muted">无填写内容</p>;
  return (
    <dl className="signature-fields">
      {entries.map(([key, value]) => (
        <div key={key}>
          <dt>{key}</dt>
          <dd>{readable(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

/* ---- 环节提交卡片 ---- */
function SubmissionCard({ item }: { item: BambooStageSubmission }) {
  return (
    <article className={item.invalidated ? "is-invalidated" : ""}>
      <header>
        <strong>{STAGE_LABELS[item.stage] ?? item.stage}</strong>
        <span>{item.actor_name || item.actor_id}</span>
        <time>{item.submitted_at ? new Date(item.submitted_at).toLocaleString() : "—"}</time>
      </header>
      {item.invalidated && <p className="signature-warning">该版本已失效，仅供追溯</p>}
      <Fields values={item.values} />
    </article>
  );
}

/* ===================================================================
 * PlantSignaturePage
 * =================================================================== */
export function PlantSignaturePage() {
  const { recordId = "" } = useParams<{ recordId: string }>();
  const { session } = useWebSession();
  const [detail, setDetail] = useState<BambooProductionDetail | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [signatureKey, setSignatureKey] = useState("");
  const [appealNote, setAppealNote] = useState("");
  const [appealIdempotencyKey, setAppealIdempotencyKey] = useState("");
  const [terminateReason, setTerminateReason] = useState("");
  const [terminateIdempotencyKey, setTerminateIdempotencyKey] = useState("");
  const [terminateConfirmOpen, setTerminateConfirmOpen] = useState(false);

  const reload = useCallback(async () => {
    if (!recordId) return;
    try {
      setDetail(await getPlantProductionDetail(recordId));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "生产记录加载失败");
    }
  }, [recordId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  /* ---- 通用操作包裹器 ---- */
  async function run(action: () => Promise<unknown>): Promise<boolean> {
    setBusy(true);
    setError("");
    try {
      await action();
      await reload();
      return true;
    } catch (cause) {
      const msg = cause instanceof Error ? cause.message : "操作失败";
      // 检测 STALE_REVISION 并提示刷新
      if (msg.includes("STALE_REVISION") || msg.includes("revision")) {
        setError("记录已被他人修改，页面已刷新至最新版本。请重新操作。");
        await reload();
      } else {
        setError(msg);
      }
      return false;
    } finally {
      setBusy(false);
    }
  }

  /* ---- 签字 ---- */
  function openSignatureConfirmation() {
    // 保持同一个 idempotency key，重复点击返回原结果
    if (!signatureKey) setSignatureKey(safeRandomUUID());
    setConfirming(true);
  }

  async function confirmSignature() {
    if (!detail || !signatureKey) return;
    const succeeded = await run(() => auditPlantRecord(
      detail.record_id,
      detail.revision,
      note,
      signatureKey,
    ));
    if (succeeded) {
      setConfirming(false);
      setSignatureKey("");
    }
  }

  /* ---- 检测终止 ---- */
  function openTerminateConfirm() {
    setTerminateReason("");
    setTerminateIdempotencyKey(safeRandomUUID());
    setTerminateConfirmOpen(true);
  }

  async function confirmTerminate() {
    if (!detail || !terminateReason.trim()) return;
    const succeeded = await run(() =>
      terminatePlantInspection(detail.record_id, terminateIdempotencyKey, terminateReason),
    );
    if (succeeded) setTerminateConfirmOpen(false);
  }

  /* ---- 上诉决定 ---- */
  async function decideAppeal(approve: boolean) {
    if (!detail) return;
    if (!appealIdempotencyKey) setAppealIdempotencyKey(safeRandomUUID());
    await run(() => decidePlantInspectionAppeal(
      detail.record_id,
      approve,
      appealNote,
      appealIdempotencyKey || safeRandomUUID(),
    ));
    setAppealNote("");
  }

  /* ---- 渲染 ---- */
  if (!detail && !error) return <div role="status" className="signature-loading">正在加载签字资料…</div>;

  const showSignButton =
    detail?.current_stage === "PLANT_AUDIT" &&
    detail?.signature_gate.can_sign;

  return (
    <section className="plant-signature-page">
      <nav><Link to="/plant/production">← 返回生产看板</Link></nav>
      {error && <div className="signature-alert" role="alert">{error}</div>}
      {detail && (
        <>
          {/* ---- 英雄头部 ---- */}
          <header className="signature-hero">
            <div>
              <span className="signature-kicker">厂长独立签字页</span>
              <h1>{detail.display_no}</h1>
              <p>笼号 {detail.cage_no || "—"} · 版本 {detail.revision} · 状态 {RECORD_STATUS_LABELS[detail.status] ?? detail.status}</p>
            </div>
            <span className="signature-stage">
              {STAGE_LABELS[detail.current_stage ?? ""] ?? detail.current_stage ?? "已完成"}
            </span>
          </header>

          {/* ---- 流程进度 ---- */}
          <section className="signature-card">
            <h2>流程进度 <small className="signature-muted">（{detail.form_type === "SORTING" ? "分选流程" : "浸胶干燥流程"}）</small></h2>
            <ol className="signature-flow">
              {STAGE_FLOW
                .filter((stage) => detail.form_type !== "SORTING" || !["DIPPING", "DRYING"].includes(stage))
                .map((stage) => (
                  <li
                    key={stage}
                    className={detail.submissions.some((item) => item.stage === stage && !item.invalidated)
                      ? "is-complete"
                      : detail.current_stage === stage
                        ? "is-current"
                        : ""}
                  >
                    {STAGE_LABELS[stage]}
                  </li>
                ))}
            </ol>
          </section>

          {/* ---- 表单基础信息 ---- */}
          <section className="signature-card">
            <h2>表单基础信息</h2>
            <Fields values={detail.base_info} />
          </section>

          {/* ---- 上游表单 ---- */}
          {detail.upstream_record && (
            <section className="signature-card">
              <h2>上游表单（只读）</h2>
              <p>{detail.upstream_record.display_no}</p>
              <Fields values={detail.upstream_record.base_info} />
              <div className="signature-submissions">
                {detail.upstream_record.submissions.map((item) => (
                  <SubmissionCard key={item.submission_id} item={item} />
                ))}
              </div>
            </section>
          )}

          {/* ---- 本表提交记录 ---- */}
          <section className="signature-card">
            <h2>本表提交记录</h2>
            <div className="signature-submissions">
              {detail.submissions.map((item) => (
                <SubmissionCard key={item.submission_id} item={item} />
              ))}
              {!detail.submissions.length && <p className="signature-muted">暂无提交记录</p>}
            </div>
          </section>

          {/* ---- 工资事实 ---- */}
          {detail.payroll_facts && detail.payroll_facts.length > 0 && (
            <section className="signature-card">
              <h2>工资影响</h2>
              <div className="signature-payroll-list">
                {detail.payroll_facts.map((fact) => (
                  <article key={fact.fact_id} className="signature-payroll-item">
                    <header>
                      <strong>{FACT_TYPE_LABELS[fact.fact_type] ?? fact.fact_type}</strong>
                      <span className="signature-payroll-amount">
                        {fact.total_amount ?? fact.amount}
                      </span>
                    </header>
                    <dl className="signature-fields">
                      <div><dt>规则</dt><dd>{fact.rule_key}</dd></div>
                      <div><dt>计量值</dt><dd>{fact.metric_value}</dd></div>
                      <div><dt>单价</dt><dd>{fact.rate}</dd></div>
                      <div><dt>基数</dt><dd>{fact.base_amount}</dd></div>
                      <div><dt>期间</dt><dd>{fact.period_start} ~ {fact.period_end}</dd></div>
                    </dl>
                    {fact.allocations && fact.allocations.length > 0 && (
                      <details className="signature-allocations">
                        <summary>分配明细（{fact.allocations.length} 人）</summary>
                        <ul>
                          {fact.allocations.map((alloc, idx) => (
                            <li key={idx}>
                              {alloc.employee_code}: {alloc.amount}
                              {alloc.rate ? `（费率 ${alloc.rate}）` : ""}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </article>
                ))}
              </div>
            </section>
          )}

          {/* ---- 检测状态 ---- */}
          <section className="signature-card">
            <h2>检测状态</h2>
            {detail.inspection_window ? (
              <>
                <div className="signature-inspection-summary">
                  <p>
                    <strong>状态：</strong>
                    <span className={`signature-inspection-status ${detail.inspection_window.status.toLowerCase()}`}>
                      {detail.inspection_window.status === "COMPLETED" ? "检测完成" :
                            detail.inspection_window.status === "EARLY_TERMINATED" ? "厂长提前结束" :
                              detail.inspection_window.status === "OPEN" ? "等待检测" :
                                detail.inspection_window.status === "CLAIMED" ? "检测中" :
                                  detail.inspection_window.status === "EXPIRED" ? "检测已过期" :
                                    detail.inspection_window.status === "APPEAL_SUBMITTED" ? "上诉待审批" :
                                      detail.inspection_window.status === "APPEAL_APPROVED" ? "上诉已批准" :
                                        detail.inspection_window.status === "APPEAL_REJECTED" ? "上诉已驳回" :
                                          detail.inspection_window.status}
                    </span>
                  </p>
                  {detail.inspection_window.remaining_seconds > 0 && detail.inspection_window.status !== "EARLY_TERMINATED" && (
                    <p className="signature-muted">
                      剩余约 {Math.ceil(detail.inspection_window.remaining_seconds / 60)} 分钟
                      {" · "}截止 {new Date(detail.inspection_window.deadline_at).toLocaleString()}
                    </p>
                  )}
                  {detail.inspection_window.appeal_deadline_at && (
                    <p className="signature-muted">上诉截止：{new Date(detail.inspection_window.appeal_deadline_at).toLocaleString()}</p>
                  )}
                  {detail.inspection_window.terminated_by && (
                    <p className="signature-muted">终止人：{detail.inspection_window.terminated_by}</p>
                  )}
                </div>

                {/* 检测详情列表 */}
                {detail.inspections.map((inspection) => (
                  <article className="signature-inspection" key={inspection.inspection_id}>
                    <header className="signature-inspection-header">
                      <strong>
                        {inspection.conclusion === "CONFORMING" ? "检测合格" :
                          inspection.conclusion === "NONCONFORMING" ? "检测不合格" :
                            inspection.conclusion}
                      </strong>
                      <span>{inspection.actor_name}</span>
                      {inspection.signed_at && (
                        <time>{new Date(inspection.signed_at).toLocaleString()}</time>
                      )}
                    </header>
                    {inspection.average_value !== undefined && (
                      <p>平均检测值：{inspection.average_value}</p>
                    )}
                    {inspection.moisture_points && inspection.moisture_points.length > 0 && (
                      <p>检测点：{inspection.moisture_points.join(", ")}</p>
                    )}
                    {inspection.note && <p className="signature-muted">备注：{inspection.note}</p>}
                    {inspection.evidence.length > 0 && (
                      <details className="signature-evidence">
                        <summary>检测证据（{inspection.evidence.length} 条）</summary>
                        <ul>
                          {inspection.evidence.map((ev) => (
                            <li key={ev.asset_id}>
                              [{ev.evidence_type}]{" "}
                              {ev.text_content || ev.file_id || ev.uri || "无内容"}
                            </li>
                          ))}
                        </ul>
                      </details>
                    )}
                  </article>
                ))}
              </>
            ) : (
              <p className="signature-muted">无检测窗口</p>
            )}

            {/* 终止检测 */}
            {["OPEN", "CLAIMED"].includes(detail.inspection_window?.status ?? "") && detail.inspection_window?.status !== "EARLY_TERMINATED" && (
              <div className="signature-terminate">
                <button type="button" className="secondary-button" disabled={busy} onClick={openTerminateConfirm}>
                  提前结束检测
                </button>
              </div>
            )}

            {/* 上诉处理 */}
            {detail.inspection_window?.status === "APPEAL_SUBMITTED" && (
              <div className="signature-appeal">
                <h3>检测上诉待审批</h3>
                {detail.inspection_window.appeal_payload?.target_stage && (
                  <p>目标环节：{STAGE_LABELS[detail.inspection_window.appeal_payload.target_stage] ?? detail.inspection_window.appeal_payload.target_stage}</p>
                )}
                {detail.inspection_window.appeal_payload?.text_evidence && (
                  <>
                    <p className="signature-appeal-label">上诉理由：</p>
                    <blockquote className="signature-appeal-quote">
                      {detail.inspection_window.appeal_payload.text_evidence}
                    </blockquote>
                  </>
                )}
                {/* 原检测值汇总 */}
                {detail.inspections.length > 0 && (
                  <details className="signature-appeal-evidence">
                    <summary>原检测记录（{detail.inspections.length} 条）</summary>
                    {detail.inspections.map((inspection) => (
                      <div key={inspection.inspection_id} className="signature-appeal-inspection">
                        <p>结论：{inspection.conclusion} · 检测人：{inspection.actor_name}</p>
                        {inspection.average_value !== undefined && <p>均值：{inspection.average_value}</p>}
                        {inspection.note && <p>备注：{inspection.note}</p>}
                        {inspection.evidence.map((ev) => (
                          <p key={ev.asset_id} className="signature-muted">
                            证据：{ev.text_content || ev.file_id || ev.evidence_type}
                          </p>
                        ))}
                      </div>
                    ))}
                  </details>
                )}
                <textarea
                  aria-label="上诉审批意见"
                  value={appealNote}
                  onChange={(event) => setAppealNote(event.target.value)}
                  placeholder="填写审批意见（可选）"
                />
                <div>
                  <button type="button" disabled={busy} onClick={() => void decideAppeal(true)}>同意上诉（重新检测）</button>
                  <button type="button" disabled={busy} onClick={() => void decideAppeal(false)}>驳回上诉</button>
                </div>
              </div>
            )}

            {/* 已判决的上诉结果 */}
            {detail.inspection_window?.appeal_decision && (
              <div className="signature-appeal-result">
                <p>
                  <strong>上诉结果：</strong>
                  {detail.inspection_window.appeal_decision === "APPROVED" ? "已批准" :
                    detail.inspection_window.appeal_decision === "REJECTED" ? "已驳回" :
                      detail.inspection_window.appeal_decision}
                </p>
                {detail.inspection_window.appeal_decision_note && (
                  <p className="signature-muted">审批意见：{detail.inspection_window.appeal_decision_note}</p>
                )}
              </div>
            )}
          </section>

          {/* ---- 厂长处理 ---- */}
          <section className="signature-card signature-actions">
            <h2>厂长处理</h2>

            {/* 签字区 */}
            <label>
              签字备注（可选）
              <textarea
                aria-label="签字备注"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </label>
            {showSignButton ? (
              <button type="button" disabled={busy} onClick={openSignatureConfirmation}>
                通过并签字
              </button>
            ) : (
              <p className="signature-warning">
                当前不可签字：{translateSignatureGateReason(detail.signature_gate.reason) || "流程条件尚未满足"}
              </p>
            )}

          </section>

          {/* 纠错案件 */}
          {detail.corrections && detail.corrections.length > 0 && (
            <section className="signature-card">
              <h2>纠错案件</h2>
              <div className="signature-corrections">
                {detail.corrections.map((c) => (
                  <article key={c.case_id} className="signature-correction-item">
                    <p><strong>案件号：</strong>{c.case_id}</p>
                    <p><strong>状态：</strong>{CORRECTION_STATUS_LABELS[c.status] ?? c.status}</p>
                    <p><strong>原因：</strong>{c.reason}</p>
                    <p className="signature-muted">创建时间：{new Date(c.created_at).toLocaleString()}</p>
                  </article>
                ))}
              </div>
            </section>
          )}

          {/* ---- 签字确认弹窗 ---- */}
          {confirming && (
            <div className="signature-dialog-backdrop" role="presentation">
              <div className="signature-dialog" role="dialog" aria-modal="true" aria-labelledby="signature-dialog-title">
                <h2 id="signature-dialog-title">签字前核对</h2>
                <dl className="signature-dialog-fields">
                  <div><dt>表号</dt><dd>{detail.display_no}</dd></div>
                  <div><dt>笼号</dt><dd>{detail.cage_no || "—"}</dd></div>
                  <div><dt>签字人</dt><dd>{session?.employee_name || session?.employee_code || "当前厂长"}</dd></div>
                  <div><dt>工厂</dt><dd>{session?.factory_name || detail.factory_id}</dd></div>
                  <div><dt>记录版本</dt><dd>{detail.revision}</dd></div>
                </dl>
                {note && <p>备注：{note}</p>}
                <div>
                  <button type="button" disabled={busy} onClick={() => void confirmSignature()}>
                    确认签字
                  </button>
                  <button type="button" disabled={busy} onClick={() => setConfirming(false)}>取消</button>
                </div>
              </div>
            </div>
          )}

          {/* ---- 终止检测确认弹窗 ---- */}
          {terminateConfirmOpen && (
            <div className="signature-dialog-backdrop" role="presentation">
              <div className="signature-dialog" role="dialog" aria-modal="true" aria-labelledby="terminate-dialog-title">
                <h2 id="terminate-dialog-title">确认提前结束检测</h2>
                <p>提前结束检测后：</p>
                <ul>
                  <li>当前检测权限结束</li>
                  <li>检测人员进入申诉窗口</li>
                  <li>厂长仍需要单独执行生产签字</li>
                  <li>操作不可直接恢复</li>
                </ul>
                <label>
                  提前结束原因（必填）
                  <textarea
                    aria-label="终止原因"
                    value={terminateReason}
                    onChange={(event) => setTerminateReason(event.target.value)}
                    placeholder="请说明终止检测的原因"
                  />
                </label>
                <div>
                  <button
                    type="button"
                    disabled={busy || !terminateReason.trim()}
                    onClick={() => void confirmTerminate()}
                  >
                    确认终止
                  </button>
                  <button type="button" disabled={busy} onClick={() => setTerminateConfirmOpen(false)}>取消</button>
                </div>
              </div>
            </div>
          )}

        </>
      )}
    </section>
  );
}
