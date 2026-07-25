import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  MobileApiError,
  mobileApiClient,
  type BambooInspection,
  type BambooOperationsSummary,
  type BambooInspectionWindow,
  type BambooNotification,
  type BambooRecord,
  type BambooStage,
} from "@form-detection/api-client";

import { createMobileClientId, getMobileDeviceId } from "../device";
import { useMobileSession } from "../session/MobileSessionProvider";
import { clearBambooDraft, readBambooDraft, writeBambooDraft, type BambooDraftScope } from "../storage/bambooDrafts";

type InspectionDraft = {
  targetStage: BambooStage;
  note: string;
  moisturePoints: number[];
  conclusion: "CONFORMING" | "NONCONFORMING" | null;
};

export function BambooOperationsPanel({
  record,
  role,
  onRefresh,
  onInspectionGateChange,
}: {
  record: BambooRecord;
  role: string;
  onRefresh(): Promise<void>;
  onInspectionGateChange?(blocked: boolean): void;
}) {
  const { sessionMetadata: session } = useMobileSession();
  const [summary, setSummary] = useState<BambooOperationsSummary | null>(null);
  const [inquiries, setInquiries] = useState<Array<{ inquiry_id: string; subject: string; status: string; messages: Array<{ actor_name: string; body: string }> }>>([]);
  const productionStages = useMemo<BambooStage[]>(() => record.form_type === "DIPPING_DRYING" ? ["DIPPING", "DRYING"] : ["SORT"], [record.form_type]);
  const [targetStage, setTargetStage] = useState<BambooStage>(() => record.form_type === "DIPPING_DRYING" ? "DRYING" : "SORT");
  const [note, setNote] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  const [audio, setAudio] = useState<File | null>(null);
  const [moisturePoints, setMoisturePoints] = useState<number[]>([]);
  const [conclusion, setConclusion] = useState<"CONFORMING" | "NONCONFORMING" | null>(null);
  const [showConfirm, setShowConfirm] = useState(false);
  const [submitSuccess, setSubmitSuccess] = useState<BambooInspection | null>(null);
  const [inspectionIdempotencyKey, setInspectionIdempotencyKey] = useState(() => createMobileClientId("inspection"));
  const [inspectionQueue, setInspectionQueue] = useState<BambooInspectionWindow[]>([]);
  const [inspectionHistory, setInspectionHistory] = useState<BambooInspectionWindow[]>([]);
  const [inspectionSearch, setInspectionSearch] = useState("");
  const [notifications, setNotifications] = useState<BambooNotification[]>([]);
  const [clock, setClock] = useState(() => Date.now());
  const [managerReply, setManagerReply] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const restoredInspection = useRef("");
  const inspectionScope = useMemo<BambooDraftScope | null>(() => session ? ({
    employeeCode: session.employee_code,
    factoryId: session.factory_id,
    deviceId: getMobileDeviceId(),
    recordId: record.record_id,
    stage: "INSPECTION",
  }) : null, [record.record_id, session]);

  // Restore inspection draft (Task 7: include moisturePoints and conclusion)
  useEffect(() => {
    if (!inspectionScope || role !== "INSPECTOR") return;
    const key = JSON.stringify(inspectionScope);
    if (restoredInspection.current === key) return;
    restoredInspection.current = key;
    const draft = readBambooDraft<InspectionDraft>(inspectionScope);
    if (!draft) return;
    setTargetStage(draft.targetStage || productionStages[0]);
    setNote(draft.note || "");
    if (Array.isArray(draft.moisturePoints)) setMoisturePoints(draft.moisturePoints);
    if (draft.conclusion) setConclusion(draft.conclusion);
  }, [inspectionScope, productionStages, role]);

  // Save inspection draft (Task 7: include moisturePoints and conclusion)
  useEffect(() => {
    if (!inspectionScope || role !== "INSPECTOR" || restoredInspection.current !== JSON.stringify(inspectionScope)) return;
    writeBambooDraft<InspectionDraft>(inspectionScope, { targetStage, note, moisturePoints, conclusion });
  }, [inspectionScope, note, role, targetStage, moisturePoints, conclusion]);

  useEffect(() => {
    const timer = window.setInterval(() => setClock(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, []);

  const load = useCallback(async () => {
    try {
      setSummary(await mobileApiClient.getBambooOperations(record.record_id));
      if (["INSPECTOR", "SUPERVISOR", "PLANT_MANAGER"].includes(role)) {
        const [active, history] = await Promise.all([
          mobileApiClient.listBambooInspectionQueue("active"),
          mobileApiClient.listBambooInspectionQueue("history"),
        ]);
        setInspectionQueue(active.items);
        setInspectionHistory(history.items);
      }
      setNotifications((await mobileApiClient.listBambooNotifications()).items);
      if (role === "PLANT_MANAGER") {
        setInquiries(await mobileApiClient.listBambooFinanceInquiries() as typeof inquiries);
      }
    } catch (cause) {
      setMessage(cause instanceof MobileApiError ? cause.problem.detail : "无法加载扩展业务信息");
    }
  }, [record.record_id, role]);

  useEffect(() => { void load(); }, [load]);

  const run = async (operation: () => Promise<unknown>, success: string) => {
    setBusy(true);
    setMessage("");
    try {
      await operation();
      setMessage(success);
      await load();
      await onRefresh();
    } catch (cause) {
      setMessage(cause instanceof MobileApiError ? cause.problem.detail : "操作失败，请重试");
    } finally {
      setBusy(false);
    }
  };

  // Task 2 & 8 & 9: Submit inspection with moisturePoints, stored idempotency key, success capture
  const submitInspection = async () => {
    if (!conclusion) return;
    setBusy(true);
    setMessage("");
    setShowConfirm(false);
    const currentConclusion = conclusion;
    try {
      const result = await mobileApiClient.submitBambooInspection(
        record.record_id,
        {
          conclusion: currentConclusion,
          targetStage: currentConclusion === "NONCONFORMING" ? targetStage : undefined,
          textEvidence: currentConclusion === "NONCONFORMING" ? note : undefined,
          photos: currentConclusion === "NONCONFORMING" ? photos : [],
          audio: currentConclusion === "NONCONFORMING" ? audio : null,
          deviceId: getMobileDeviceId(),
          moisturePoints,
        },
        inspectionIdempotencyKey,
      );
      if (inspectionScope) clearBambooDraft(inspectionScope);
      setSubmitSuccess(result);
      // Task 8: regenerate idempotency key after success for next submission
      setInspectionIdempotencyKey(createMobileClientId("inspection"));
      setNote("");
      setPhotos([]);
      setAudio(null);
      setConclusion(null);
      setMoisturePoints([0, 0, 0]);
      await load();
      await onRefresh();
    } catch (cause) {
      setMessage(cause instanceof MobileApiError ? cause.problem.detail : "操作失败，请重试");
    } finally {
      setBusy(false);
    }
  };

  const payrollFacts = summary?.payroll_facts ?? [];
  const inspections = summary?.inspections ?? [];
  const visibleInspectionQueue = inspectionQueue.filter((item) => {
    const query = inspectionSearch.trim().toLocaleLowerCase();
    return !query || item.display_no.toLocaleLowerCase().includes(query) || item.cage_no.toLocaleLowerCase().includes(query);
  });
  const currentWindow = [...inspectionQueue, ...inspectionHistory].find((item) => item.record_id === record.record_id);
  const claimedByMe = currentWindow?.claimed_by === session?.employee_code;
  const remainingSeconds = currentWindow
    ? Math.max(0, Math.ceil((new Date(currentWindow.deadline_at).getTime() - clock) / 1000))
    : 0;

  const moistureAvg = useMemo(
    () => moisturePoints.length > 0
      ? (moisturePoints.reduce((a, b) => a + b, 0) / moisturePoints.length).toFixed(1)
      : null,
    [moisturePoints],
  );

  useEffect(() => {
    onInspectionGateChange?.(
      Boolean(currentWindow && ["OPEN", "CLAIMED", "APPEAL_SUBMITTED"].includes(currentWindow.status)),
    );
  }, [currentWindow, onInspectionGateChange]);

  // ── Shared render helpers ──

  const payrollFactsSection = (label: string) => (
    <section className="bamboo-sheet-section bamboo-operations-panel">
      <h3>{label}</h3>
      {payrollFacts.length === 0 ? (
        <p>{record.form_type === "DIPPING_DRYING"
          ? "本联合表在浸胶记录与干燥联合签字完成后生成工资事实。"
          : "本分选表签字后生成独立工资事实，厂长确认后生效。"}</p>
      ) : payrollFacts.map((fact) => (
        <article className="bamboo-operation-card" key={fact.fact_id}>
          <strong>{fact.fact_type === "SORT" ? "分选工资" : "浸胶＋干燥联合工资"}：¥{fact.total_amount}</strong>
          <span>{fact.status === "EFFECTIVE" ? "厂长确认后已生效" : fact.status === "INVALIDATED" ? "已作废" : "待厂长确认生效"}</span>
          <ul>{fact.allocations.map((item) => <li key={`${fact.fact_id}-${item.employee_code}`}>{item.employee_code}：¥{item.amount}</li>)}</ul>
        </article>
      ))}
    </section>
  );

  const existingInspectionsList = () => inspections.map((inspection) => (
    <article className="bamboo-operation-card" key={inspection.inspection_id}>
      <strong>{inspection.serial_no} · {inspection.target_stage} · 平均 {inspection.average_value}</strong>
      <span>{inspection.conclusion === "CONFORMING" ? "合格" : "异常"} · {inspection.actor_name}</span>
      <p>{inspection.note}</p>
      <p>留痕：{inspection.evidence.map((item) => item.evidence_type).join("、") || "无"}</p>
    </article>
  ));

  const inspectionQueueBlock = () => (
    role === "INSPECTOR" && inspectionQueue.length > 0 && (
      <div className="bamboo-inspection-queue" aria-label="本厂检测队列">
        <label>搜索表号或笼号<input type="search" value={inspectionSearch} onChange={(event) => setInspectionSearch(event.target.value)} placeholder="可选，不搜索时显示全部" /></label>
        {visibleInspectionQueue.map((item) => (
          <article className={item.record_id === record.record_id ? "current" : ""} key={item.record_id}>
            <strong>{item.display_no}</strong><span>笼号 {item.cage_no}</span>
          </article>
        ))}
        {visibleInspectionQueue.length === 0 && <p>没有匹配的待检表单</p>}
      </div>
    )
  );

  const windowStatusBlock = () => (
    currentWindow && (
      <div className="bamboo-window-status">
        <strong>{currentWindow.inside_window ? `检测剩余时间 ${formatDuration(remainingSeconds)}` : "两小时检测已结束"}</strong>
        <span>{inspectionStatus(currentWindow.status)}</span>
      </div>
    )
  );

  // ── Main render ──

  return (
    <>
      {message && <div className="mobile-status-banner" role="status">{message}</div>}

      {/* ═══ Task 3: INSPECTOR — inspection FIRST, payroll LAST ═══ */}
      {role === "INSPECTOR" && (
        <>
          {/* Task 9: Success state */}
          {submitSuccess && (
            <section className="bamboo-sheet-section bamboo-inspection-success">
              <h3>检测已提交</h3>
              <dl className="bamboo-sheet-grid">
                <div><dt>检测序号</dt><dd>{submitSuccess.serial_no}</dd></div>
                <div><dt>检测环节</dt><dd>{submitSuccess.target_stage}</dd></div>
                <div><dt>检测结论</dt><dd>{submitSuccess.conclusion === "CONFORMING" ? "合格" : "异常"}</dd></div>
                <div><dt>平均值</dt><dd>{submitSuccess.average_value}</dd></div>
                <div><dt>检测人</dt><dd>{submitSuccess.actor_name}</dd></div>
                <div><dt>留痕</dt><dd>{submitSuccess.evidence.map((item) => item.evidence_type).join("、") || "无"}</dd></div>
                {submitSuccess.note && <div><dt>备注</dt><dd>{submitSuccess.note}</dd></div>}
              </dl>
              <button type="button" className="btn secondary" onClick={() => setSubmitSuccess(null)}>关闭</button>
            </section>
          )}

          <section className="bamboo-sheet-section bamboo-operations-panel">
            <h3>检测与证据留痕</h3>
            {inspectionQueueBlock()}
            {windowStatusBlock()}
            {role === "INSPECTOR" && summary && !currentWindow && (
              <div className="card empty" style={{ margin: "12px 0" }}>
                <h3>当前记录尚未生成检测窗口</h3>
                <p>请确认生产工序已完成提交。如已提交，请联系主管或管理员确认检测窗口状态。</p>
              </div>
            )}
            {existingInspectionsList()}

            {currentWindow?.status === "OPEN" && (
              <button className="bamboo-sign-button" disabled={busy} onClick={() => void run(
                () => mobileApiClient.claimBambooInspection(record.record_id, createMobileClientId("inspection-claim")),
                "已领取本表检测权",
              )}>领取检测</button>
            )}

            {/* Task 1, 2, 4: Full inspection form */}
            {currentWindow?.status === "CLAIMED" && claimedByMe && currentWindow.inside_window && (
              <div className="bamboo-operation-form">
                {/* Task 1: Moisture points */}
                <fieldset className="bamboo-moisture-fieldset">
                  <legend>含水率检测点（%）</legend>
                  <div className="bamboo-moisture-grid">
                    {moisturePoints.map((value, index) => (
                      <label key={index}>
                        <span>检测点 {index + 1}</span>
                        <input
                          aria-label={`含水率检测点 ${index + 1}`}
                          type="number"
                          step="1"
                          min="1"
                          max="100"
                          inputMode="numeric"
                          value={value || ""}
                          onChange={(event) => setMoisturePoints(moisturePoints.map((item, itemIndex) => itemIndex === index ? Number(event.target.value) : item))}
                        />
                      </label>
                    ))}
                  </div>
                  <div className="bamboo-point-actions">
                    <button type="button" disabled={moisturePoints.length >= 20} onClick={() => setMoisturePoints([...moisturePoints, 0])}>增加检测点</button>
                    <button type="button" disabled={moisturePoints.length === 0} onClick={() => setMoisturePoints(moisturePoints.slice(0, -1))}>删除最后一个</button>
                  </div>
                  <p className="bamboo-moisture-average">已填写 {moisturePoints.length} 点 · 平均值 {moistureAvg ?? "—"}%</p>
                </fieldset>

                {/* Task 4: Radio group for conclusion */}
                <fieldset className="bamboo-conclusion-fieldset">
                  <legend>检测结论 *</legend>
                  <label className="bamboo-radio-label">
                    <input type="radio" name="conclusion" value="CONFORMING" checked={conclusion === "CONFORMING"} onChange={() => setConclusion("CONFORMING")} /> 合格
                  </label>
                  <label className="bamboo-radio-label">
                    <input type="radio" name="conclusion" value="NONCONFORMING" checked={conclusion === "NONCONFORMING"} onChange={() => setConclusion("NONCONFORMING")} /> 不合格
                  </label>
                </fieldset>

                {conclusion === "CONFORMING" && (
                  <label>备注（选填）<textarea value={note} onChange={(event) => setNote(event.target.value)} placeholder="可选备注…" /></label>
                )}

                {conclusion === "NONCONFORMING" && (
                  <>
                    <label>检测目标<select value={targetStage} onChange={(event) => setTargetStage(event.target.value as BambooStage)}>{productionStages.map((stage) => <option value={stage} key={stage}>{stageLabel(stage)}</option>)}</select></label>
                    <label>文字检测结果<textarea value={note} onChange={(event) => setNote(event.target.value)} /></label>
                    <label className="bamboo-capture-button" role="button" tabIndex={0}>点击拍照<input hidden type="file" accept="image/*" capture="environment" multiple onChange={(event) => setPhotos(Array.from(event.target.files ?? []))} /></label>
                    <label className="bamboo-capture-button" role="button" tabIndex={0}>点击录音<input hidden type="file" accept="audio/*" capture onChange={(event) => setAudio(event.target.files?.[0] ?? null)} /></label>
                    <small>{photos.length ? `已选择 ${photos.length} 张照片` : "未选择照片"} · {audio ? "已录音" : "未录音"}</small>
                  </>
                )}

                <button className="bamboo-sign-button" disabled={busy || !conclusion} onClick={() => setShowConfirm(true)}>核对并提交检测记录</button>

                {/* Task 5: Pre-submit confirmation */}
                {showConfirm && (
                  <div className="bamboo-v3-sheet-backdrop" role="presentation">
                    <div className="bamboo-v3-bottom-sheet bamboo-stage-confirm-sheet" role="dialog" aria-modal="true" aria-labelledby="inspectionConfirmTitle">
                      <div className="bamboo-v3-sheet-handle" />
                      <header>
                        <h3 id="inspectionConfirmTitle">核对并提交检测记录</h3>
                        <button type="button" aria-label="关闭" onClick={() => setShowConfirm(false)} disabled={busy}>×</button>
                      </header>
                      <dl className="bamboo-sheet-grid bamboo-confirm-values">
                        <div><dt>表号</dt><dd>{record.display_no}</dd></div>
                        <div><dt>笼号</dt><dd>{String(record.base_info.cage_no ?? "—")}</dd></div>
                        <div><dt>检测环节</dt><dd>{targetStage ? stageLabel(targetStage) : "—"}</dd></div>
                        <div><dt>检测人</dt><dd>{session?.employee_name || "—"}</dd></div>
                        <div><dt>检测点数量</dt><dd>{moisturePoints.length}</dd></div>
                        <div><dt>平均值</dt><dd>{moistureAvg ? `${moistureAvg}%` : "—"}</dd></div>
                        <div><dt>检测结论</dt><dd>{conclusion === "CONFORMING" ? "合格" : "不合格"}</dd></div>
                        {conclusion === "NONCONFORMING" && (
                          <>
                            <div><dt>异常说明</dt><dd>{note || "无"}</dd></div>
                            <div><dt>照片数量</dt><dd>{photos.length}</dd></div>
                            <div><dt>录音</dt><dd>{audio ? "有" : "无"}</dd></div>
                          </>
                        )}
                      </dl>
                      <div className="btnrow">
                        <button type="button" className="btn secondary" onClick={() => setShowConfirm(false)} disabled={busy}>返回修改</button>
                        <button type="button" className="btn primary" onClick={() => void submitInspection()} disabled={busy}>
                          {busy ? "提交中…" : "确认提交"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {currentWindow && ["EARLY_TERMINATED", "EXPIRED"].includes(currentWindow.status) && (
              <button disabled={busy} onClick={() => void run(
                () => mobileApiClient.claimBambooInspectionAppeal(record.record_id),
                "已领取24小时申诉权",
              )}>领取申诉</button>
            )}
            {currentWindow?.status === "APPEAL_CLAIMED" && currentWindow.appeal_claimed_by === session?.employee_code && (
              <div className="bamboo-operation-form">
                <label>申诉环节<select value={targetStage} onChange={(event) => setTargetStage(event.target.value as BambooStage)}>{productionStages.map((stage) => <option value={stage} key={stage}>{stageLabel(stage)}</option>)}</select></label>
                <label>申诉检测结果<textarea value={note} onChange={(event) => setNote(event.target.value)} /></label>
                <button disabled={busy || !note.trim()} onClick={() => void run(
                  () => mobileApiClient.submitBambooInspectionAppeal(record.record_id, targetStage, note),
                  "申诉已提交厂长审批",
                )}>提交申诉</button>
              </div>
            )}
          </section>

          {/* Task 3: Payroll facts LAST for INSPECTOR */}
          {payrollFactsSection("工资事实（仅供核对）")}
        </>
      )}

      {/* ═══ Non-INSPECTOR: original ordering ═══ */}
      {role !== "INSPECTOR" && (
        <>
          {payrollFactsSection("工资事实")}

          {inspections.length > 0 && (
            <section className="bamboo-sheet-section bamboo-operations-panel">
              <h3>检测与证据留痕</h3>
              {windowStatusBlock()}
              {existingInspectionsList()}
            </section>
          )}

          {role === "PLANT_MANAGER" && currentWindow && ["OPEN", "CLAIMED"].includes(currentWindow.status) && (
            <section className="bamboo-sheet-section bamboo-operations-panel">
              <h3>检测窗口管理</h3>
              <p>检测窗口结束前不能直接签字。确需提前签字时，将立即停止检测权限并通知所有检测员。</p>
              <button className="btn danger" disabled={busy} onClick={() => {
                if (window.confirm("确认提前停止检测并开放厂长确认？")) void run(
                  () => mobileApiClient.terminateBambooInspection(record.record_id),
                  "检测已终止，已通知检测员",
                );
              }}>停止检测并提前签字</button>
            </section>
          )}
          {role === "PLANT_MANAGER" && currentWindow?.status === "APPEAL_SUBMITTED" && (
            <section className="bamboo-sheet-section bamboo-operations-panel">
              <h3>检测申诉审批</h3>
              <label>审批说明<textarea value={note} onChange={(event) => setNote(event.target.value)} /></label>
              <div className="btnrow">
                <button disabled={busy} className="btn secondary" onClick={() => void run(
                  () => mobileApiClient.decideBambooInspectionAppeal(record.record_id, false, note),
                  "申诉已驳回",
                )}>驳回申诉</button>
              </div>
            </section>
          )}

          {role === "SUPERVISOR" && (
            <section className="bamboo-sheet-section bamboo-operations-panel">
              <h3>主管处理</h3>
              {inspections.filter((item) => item.exception?.status === "OPEN").map((item) => <div className="error-banner" role="alert" key={item.inspection_id}>存在未关闭的检测异常（{item.serial_no}），请先处理后再签字</div>)}
              {(summary?.corrections ?? []).filter((item) => item.status === "OPEN").map((item) => <div className="error-banner" key={item.case_id}>财务要求纠错：{item.reason}</div>)}
            </section>
          )}
        </>
      )}

      {/* ═══ Common sections (all roles) ═══ */}
      {role === "PLANT_MANAGER" && inquiries.length > 0 && (
        <section className="bamboo-sheet-section bamboo-operations-panel">
          <h3>财务回溯询问</h3>
          {inquiries.map((inquiry) => <article className="bamboo-operation-card" key={inquiry.inquiry_id}><strong>{inquiry.subject}</strong><span>{inquiry.status}</span>{inquiry.messages.map((item, index) => <p key={`${inquiry.inquiry_id}-${index}`}>{item.actor_name}：{item.body}</p>)}{inquiry.status !== "CLOSED" && <div className="bamboo-operation-form"><textarea placeholder="向财务说明具体情况" value={managerReply} onChange={(event) => setManagerReply(event.target.value)} /><button disabled={busy || !managerReply} onClick={() => void run(() => mobileApiClient.replyBambooFinanceInquiry(inquiry.inquiry_id, managerReply), "说明已回复财务")}>回复财务</button></div>}</article>)}
        </section>
      )}

      {notifications.length > 0 && (
        <section className="bamboo-sheet-section bamboo-operations-panel">
          <h3>消息中心</h3>
          {notifications.map((item) => <article className="bamboo-operation-card" key={item.notification_id}><strong>{item.title}</strong><p>{item.body}</p><time>{new Date(item.created_at).toLocaleString("zh-CN")}</time></article>)}
        </section>
      )}
    </>
  );
}

function stageLabel(stage: BambooStage): string {
  return ({ SORT: "分选", DIPPING: "浸胶", DRYING: "干燥", SUPERVISOR: "主管审核", PLANT_AUDIT: "厂长确认" })[stage];
}

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const rest = seconds % 60;
  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function inspectionStatus(status: string): string {
  return ({ OPEN: "待领取", CLAIMED: "检测中", COMPLETED: "检测完成", EARLY_TERMINATED: "厂长提前终止", EXPIRED: "检测超时", APPEAL_CLAIMED: "申诉填写中", APPEAL_SUBMITTED: "申诉待审批", APPEAL_APPROVED: "申诉已通过", APPEAL_REJECTED: "申诉已驳回" } as Record<string, string>)[status] ?? status;
}
