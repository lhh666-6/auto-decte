import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  MobileApiError,
  mobileApiClient,
  type BambooOperationsSummary,
  type BambooInspectionWindow,
  type BambooNotification,
  type BambooRecord,
  type BambooStage,
} from "@form-detection/api-client";

import { createMobileClientId, getMobileDeviceId } from "../device";
import { useMobileSession } from "../session/MobileSessionProvider";
import { clearBambooDraft, readBambooDraft, writeBambooDraft, type BambooDraftScope } from "../storage/bambooDrafts";

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
  const [targetStage, setTargetStage] = useState<BambooStage>(() => record.form_type === "DIPPING_DRYING" ? "DIPPING" : "SORT");
  const [note, setNote] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  const [audio, setAudio] = useState<File | null>(null);
  const [abnormalOpen, setAbnormalOpen] = useState(false);
  const [inspectionQueue, setInspectionQueue] = useState<BambooInspectionWindow[]>([]);
  const [inspectionHistory, setInspectionHistory] = useState<BambooInspectionWindow[]>([]);
  const [inspectionSearch, setInspectionSearch] = useState("");
  const [notifications, setNotifications] = useState<BambooNotification[]>([]);
  const [clock, setClock] = useState(() => Date.now());
  const [returnStages, setReturnStages] = useState<BambooStage[]>([]);
  const [returnReason, setReturnReason] = useState("");
  const [returnOpen, setReturnOpen] = useState(false);
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

  useEffect(() => {
    if (!inspectionScope || role !== "INSPECTOR") return;
    const key = JSON.stringify(inspectionScope);
    if (restoredInspection.current === key) return;
    restoredInspection.current = key;
    const draft = readBambooDraft<{ targetStage: BambooStage; note: string }>(inspectionScope);
    if (!draft) return;
    setTargetStage(draft.targetStage || productionStages[0]);
    setNote(draft.note || "");
  }, [inspectionScope, productionStages, role]);

  useEffect(() => {
    if (!inspectionScope || role !== "INSPECTOR" || restoredInspection.current !== JSON.stringify(inspectionScope)) return;
    writeBambooDraft(inspectionScope, { targetStage, note });
  }, [inspectionScope, note, role, targetStage]);

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

  const submitInspection = (result: "CONFORMING" | "NONCONFORMING") => run(async () => {
    await mobileApiClient.submitBambooInspection(
      record.record_id,
      {
        conclusion: result,
        targetStage: result === "NONCONFORMING" ? targetStage : undefined,
        textEvidence: result === "NONCONFORMING" ? note : undefined,
        photos: result === "NONCONFORMING" ? photos : [],
        audio: result === "NONCONFORMING" ? audio : null,
        deviceId: getMobileDeviceId(),
      },
      createMobileClientId("inspection"),
    );
    if (inspectionScope) clearBambooDraft(inspectionScope);
    setNote("");
    setPhotos([]);
    setAudio(null);
    setAbnormalOpen(false);
  }, result === "CONFORMING" ? "检测合格" : "异常检测结果及留痕已保存");

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

  useEffect(() => {
    onInspectionGateChange?.(
      Boolean(currentWindow && ["OPEN", "CLAIMED", "APPEAL_SUBMITTED"].includes(currentWindow.status)),
    );
  }, [currentWindow, onInspectionGateChange]);

  return (
    <>
      {message && <div className="mobile-status-banner" role="status">{message}</div>}

      <section className="bamboo-sheet-section bamboo-operations-panel">
        <h3>工资事实</h3>
        {payrollFacts.length === 0 ? <p>{record.form_type === "DIPPING_DRYING" ? "本联合表在浸胶记录与干燥联合签字完成后生成工资事实。" : "本分选表签字后生成独立工资事实，厂长审核后生效。"}</p> : payrollFacts.map((fact) => (
          <article className="bamboo-operation-card" key={fact.fact_id}>
            <strong>{fact.fact_type === "SORT" ? "分选工资" : "浸胶＋干燥联合工资"}：¥{fact.total_amount}</strong>
            <span>{fact.status === "EFFECTIVE" ? "厂长审核后已生效" : fact.status === "INVALIDATED" ? "已因回退作废" : "待厂长审核生效"}</span>
            <ul>{fact.allocations.map((item) => <li key={`${fact.fact_id}-${item.employee_code}`}>{item.employee_code}：¥{item.amount}</li>)}</ul>
          </article>
        ))}
      </section>

      {(role === "INSPECTOR" || inspections.length > 0) && (
        <section className="bamboo-sheet-section bamboo-operations-panel">
          <h3>检测与证据留痕</h3>
          {role === "INSPECTOR" && inspectionQueue.length > 0 && (
            <div className="bamboo-inspection-queue" aria-label="本厂检测队列">
              <label>搜索表号或笼号<input type="search" value={inspectionSearch} onChange={(event) => setInspectionSearch(event.target.value)} placeholder="可选，不搜索时显示全部" /></label>
              {visibleInspectionQueue.map((item) => (
                <article className={item.record_id === record.record_id ? "current" : ""} key={item.record_id}>
                  <strong>{item.display_no}</strong><span>笼号 {item.cage_no}</span>
                </article>
              ))}
              {visibleInspectionQueue.length === 0 && <p>没有匹配的待检表单</p>}
            </div>
          )}
          {currentWindow && (
            <div className="bamboo-window-status">
              <strong>{currentWindow.inside_window ? `检测剩余时间 ${formatDuration(remainingSeconds)}` : "两小时检测已结束"}</strong>
              <span>{inspectionStatus(currentWindow.status)}</span>
            </div>
          )}
          {inspections.map((inspection) => (
            <article className="bamboo-operation-card" key={inspection.inspection_id}>
              <strong>{inspection.serial_no} · {inspection.target_stage} · 平均 {inspection.average_value}</strong>
              <span>{inspection.conclusion === "CONFORMING" ? "合格" : "异常"} · {inspection.actor_name}</span>
              <p>{inspection.note}</p>
              <p>留痕：{inspection.evidence.map((item) => item.evidence_type).join("、") || "无"}</p>
              {inspection.exception?.status === "OPEN" && role === "INSPECTOR" && (
                <button disabled={busy} onClick={() => void run(
                  () => mobileApiClient.closeBambooException(inspection.exception!.exception_id, "复测后关闭"),
                  "异常已关闭，主管可以继续审核",
                )}>复测合格并关闭异常</button>
              )}
            </article>
          ))}
          {role === "INSPECTOR" && currentWindow?.status === "OPEN" && (
            <button className="bamboo-sign-button" disabled={busy} onClick={() => void run(
              () => mobileApiClient.claimBambooInspection(record.record_id, createMobileClientId("inspection-claim")),
              "已领取本表检测权",
            )}>领取检测</button>
          )}
          {role === "INSPECTOR" && currentWindow?.status === "CLAIMED" && claimedByMe && currentWindow.inside_window && (
            <div className="bamboo-operation-form">
              <button className="bamboo-sign-button" disabled={busy} onClick={() => void submitInspection("CONFORMING")}>检测合格</button>
              <button type="button" className="btn secondary" onClick={() => setAbnormalOpen((value) => !value)}>报告异常</button>
              {abnormalOpen && <>
                <label>检测目标<select value={targetStage} onChange={(event) => setTargetStage(event.target.value as BambooStage)}>{productionStages.map((stage) => <option value={stage} key={stage}>{stageLabel(stage)}</option>)}</select></label>
                <label>文字检测结果<textarea value={note} onChange={(event) => setNote(event.target.value)} /></label>
                <label className="bamboo-capture-button" role="button" tabIndex={0}>点击拍照<input hidden type="file" accept="image/*" capture="environment" multiple onChange={(event) => setPhotos(Array.from(event.target.files ?? []))} /></label>
                <label className="bamboo-capture-button" role="button" tabIndex={0}>点击录音<input hidden type="file" accept="audio/*" capture onChange={(event) => setAudio(event.target.files?.[0] ?? null)} /></label>
                <small>{photos.length ? `已选择 ${photos.length} 张照片` : "未选择照片"} · {audio ? "已录音" : "未录音"}</small>
                <button className="btn danger" disabled={busy || (!note.trim() && photos.length === 0 && !audio)} onClick={() => void submitInspection("NONCONFORMING")}>提交异常检测</button>
              </>}
            </div>
          )}
          {role === "INSPECTOR" && currentWindow && ["EARLY_TERMINATED", "EXPIRED"].includes(currentWindow.status) && (
            <button disabled={busy} onClick={() => void run(
              () => mobileApiClient.claimBambooInspectionAppeal(record.record_id),
              "已领取24小时申诉权",
            )}>领取申诉</button>
          )}
          {role === "INSPECTOR" && currentWindow?.status === "APPEAL_CLAIMED" && currentWindow.appeal_claimed_by === session?.employee_code && (
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
      )}

      {role === "PLANT_MANAGER" && currentWindow && ["OPEN", "CLAIMED"].includes(currentWindow.status) && (
        <section className="bamboo-sheet-section bamboo-operations-panel">
          <h3>检测窗口管理</h3>
          <p>检测窗口结束前不能直接签字。确需提前签字时，将立即停止检测权限并通知所有检测员。</p>
          <button className="btn danger" disabled={busy} onClick={() => {
            if (window.confirm("确认提前停止检测并开放厂长签字？")) void run(
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
            <button disabled={busy} className="btn danger" onClick={() => void run(
              () => mobileApiClient.decideBambooInspectionAppeal(record.record_id, true, note),
              "申诉已通过，表单已回溯",
            )}>通过并回溯</button>
          </div>
        </section>
      )}

      {role === "SUPERVISOR" && (
        <section className="bamboo-sheet-section bamboo-operations-panel">
          <h3>主管处理</h3>
          {(summary?.corrections ?? []).filter((item) => item.status === "OPEN").map((item) => <div className="error-banner" key={item.case_id}>财务要求纠错：{item.reason}</div>)}
          {!returnOpen ? (
            <><p>核对无误请直接使用下方“通过并签字”。只有发现错误时才发起回退。</p><button type="button" className="btn secondary" onClick={() => setReturnOpen(true)}>发现问题，发起回退</button></>
          ) : (
            <div className="bamboo-operation-form">
              <p>只勾选确实需要重写的工序；旧版本仍保留用于审计。</p>
              <div className="bamboo-return-options">
                {productionStages.map((stage) => (
                  <label key={stage}><input type="checkbox" checked={returnStages.includes(stage)} onChange={(event) => setReturnStages(event.target.checked ? [...returnStages, stage] : returnStages.filter((item) => item !== stage))} />{stageLabel(stage)}</label>
                ))}
              </div>
              <label>回退原因<textarea value={returnReason} onChange={(event) => setReturnReason(event.target.value)} /></label>
              <div className="btnrow"><button type="button" className="btn secondary" onClick={() => setReturnOpen(false)} disabled={busy}>取消回退</button><button type="button" className="btn danger" disabled={busy || returnStages.length === 0 || !returnReason} onClick={() => void run(() => mobileApiClient.returnBambooRecord(record.record_id, returnStages, returnReason), "已按选择回退")}>确认回退</button></div>
            </div>
          )}
        </section>
      )}



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
  return ({ SORT: "分选", DIPPING: "浸胶", DRYING: "干燥", SUPERVISOR: "主管审核", PLANT_AUDIT: "厂长审核" })[stage];
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
