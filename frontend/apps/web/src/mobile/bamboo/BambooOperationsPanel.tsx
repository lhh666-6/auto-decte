import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  MobileApiError,
  mobileApiClient,
  type BambooOperationsSummary,
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
}: {
  record: BambooRecord;
  role: string;
  onRefresh(): Promise<void>;
}) {
  const { sessionMetadata: session } = useMobileSession();
  const [summary, setSummary] = useState<BambooOperationsSummary | null>(null);
  const [inquiries, setInquiries] = useState<Array<{ inquiry_id: string; subject: string; status: string; messages: Array<{ actor_name: string; body: string }> }>>([]);
  const [serialNo, setSerialNo] = useState("");
  const productionStages = useMemo<BambooStage[]>(() => record.form_type === "DIPPING_DRYING" ? ["DIPPING", "DRYING"] : ["SORT"], [record.form_type]);
  const [targetStage, setTargetStage] = useState<BambooStage>(() => record.form_type === "DIPPING_DRYING" ? "DIPPING" : "SORT");
  const [points, setPoints] = useState("");
  const [conclusion, setConclusion] = useState("CONFORMING");
  const [note, setNote] = useState("");
  const [evidenceFiles, setEvidenceFiles] = useState<File[]>([]);
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
    const draft = readBambooDraft<{ serialNo: string; targetStage: BambooStage; points: string; conclusion: string; note: string }>(inspectionScope);
    if (!draft) return;
    setSerialNo(draft.serialNo || "");
    setTargetStage(draft.targetStage || productionStages[0]);
    setPoints(draft.points || "");
    setConclusion(draft.conclusion || "CONFORMING");
    setNote(draft.note || "");
  }, [inspectionScope, productionStages, role]);

  useEffect(() => {
    if (!inspectionScope || role !== "INSPECTOR" || restoredInspection.current !== JSON.stringify(inspectionScope)) return;
    writeBambooDraft(inspectionScope, { serialNo, targetStage, points, conclusion, note });
  }, [conclusion, inspectionScope, note, points, role, serialNo, targetStage]);

  const load = useCallback(async () => {
    try {
      setSummary(await mobileApiClient.getBambooOperations(record.record_id));
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

  const createInspection = () => run(async () => {
    const created = await mobileApiClient.createBambooInspection(
      record.record_id,
      {
        serial_no: serialNo,
        target_stage: targetStage,
        moisture_points: points.split(/[，,\s]+/).filter(Boolean).map(Number),
        conclusion,
        note,
        text_evidence: note,
        device_id: getMobileDeviceId(),
      },
      createMobileClientId("inspection"),
    );
    for (const file of evidenceFiles) {
      await mobileApiClient.uploadBambooEvidence(
        created.inspection_id,
        file.type.startsWith("audio/") ? "AUDIO" : "PHOTO",
        file,
        createMobileClientId("evidence"),
      );
    }
    if (inspectionScope) clearBambooDraft(inspectionScope);
    setSerialNo("");
    setPoints("");
    setNote("");
    setEvidenceFiles([]);
  }, "检测记录及留痕已保存");

  const payrollFacts = summary?.payroll_facts ?? [];
  const inspections = summary?.inspections ?? [];

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
          {role === "INSPECTOR" && record.current_stage === "SUPERVISOR" && (
            <div className="bamboo-operation-form">
              <label>检测序号<input value={serialNo} onChange={(event) => setSerialNo(event.target.value)} /></label>
              <label>检测目标<select value={targetStage} onChange={(event) => setTargetStage(event.target.value as BambooStage)}>{productionStages.map((stage) => <option value={stage} key={stage}>{stageLabel(stage)}</option>)}</select></label>
              <label>检测数值（逗号分隔）<input inputMode="decimal" value={points} onChange={(event) => setPoints(event.target.value)} /></label>
              <label>结论<select value={conclusion} onChange={(event) => setConclusion(event.target.value)}><option value="CONFORMING">合格</option><option value="NONCONFORMING">不合格</option></select></label>
              <label>文字留痕<textarea value={note} onChange={(event) => setNote(event.target.value)} /></label>
              <label>照片或录音<input type="file" accept="image/*,audio/*" multiple onChange={(event) => setEvidenceFiles(Array.from(event.target.files ?? []))} /></label>
              <button className="bamboo-sign-button" disabled={busy || !serialNo || !points} onClick={() => void createInspection()}>保存检测并签字</button>
            </div>
          )}
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
    </>
  );
}

function stageLabel(stage: BambooStage): string {
  return ({ SORT: "分选", DIPPING: "浸胶", DRYING: "干燥", SUPERVISOR: "主管审核", PLANT_AUDIT: "厂长审核" })[stage];
}
