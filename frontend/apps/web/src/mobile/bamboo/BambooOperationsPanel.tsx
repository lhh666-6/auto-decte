import { useCallback, useEffect, useState } from "react";

import {
  MobileApiError,
  mobileApiClient,
  type BambooDailyBatch,
  type BambooOperationsSummary,
  type BambooRecord,
  type BambooRoleChange,
  type BambooStage,
} from "@form-detection/api-client";

import { getMobileDeviceId } from "../device";

const WORKER_ROLES = ["SORT_OPERATOR", "DIPPING_OPERATOR", "DRYING_RACK_OPERATOR"];

export function BambooOperationsPanel({
  record,
  role,
  onRefresh,
}: {
  record: BambooRecord;
  role: string;
  onRefresh(): Promise<void>;
}) {
  const [summary, setSummary] = useState<BambooOperationsSummary | null>(null);
  const [batches, setBatches] = useState<BambooDailyBatch[]>([]);
  const [roleChanges, setRoleChanges] = useState<BambooRoleChange[]>([]);
  const [inquiries, setInquiries] = useState<Array<{ inquiry_id: string; subject: string; status: string; messages: Array<{ actor_name: string; body: string }> }>>([]);
  const [serialNo, setSerialNo] = useState("");
  const [targetStage, setTargetStage] = useState<BambooStage>("DRYING");
  const [points, setPoints] = useState("");
  const [conclusion, setConclusion] = useState("CONFORMING");
  const [note, setNote] = useState("");
  const [evidenceFiles, setEvidenceFiles] = useState<File[]>([]);
  const [returnStages, setReturnStages] = useState<BambooStage[]>([]);
  const [returnReason, setReturnReason] = useState("");
  const [newRole, setNewRole] = useState("");
  const [roleReason, setRoleReason] = useState("");
  const [financeNote, setFinanceNote] = useState("");
  const [managerReply, setManagerReply] = useState("");
  const [employeeCode, setEmployeeCode] = useState("");
  const [assignmentRole, setAssignmentRole] = useState("");
  const [sortRate, setSortRate] = useState("1.00");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  const load = useCallback(async () => {
    try {
      setSummary(await mobileApiClient.getBambooOperations(record.record_id));
      if (role === "FINANCE_APPROVER") {
        setBatches(await mobileApiClient.listBambooDailyBatches());
      }
      if (role === "PLANT_MANAGER") {
        setRoleChanges(await mobileApiClient.listBambooRoleChanges());
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
      crypto.randomUUID(),
    );
    for (const file of evidenceFiles) {
      await mobileApiClient.uploadBambooEvidence(
        created.inspection_id,
        file.type.startsWith("audio/") ? "AUDIO" : "PHOTO",
        file,
        crypto.randomUUID(),
      );
    }
  }, "检测记录及留痕已保存");

  const payrollFacts = summary?.payroll_facts ?? [];
  const inspections = summary?.inspections ?? [];
  const financeItems = batches.flatMap((batch) => batch.items).filter((item) => item.record_id === record.record_id);

  return (
    <>
      {message && <div className="mobile-status-banner" role="status">{message}</div>}

      <section className="bamboo-sheet-section bamboo-operations-panel">
        <h3>工资事实</h3>
        {payrollFacts.length === 0 ? <p>工资将在分选签字、浸胶与干燥共同签字后生成。</p> : payrollFacts.map((fact) => (
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
              <label>检测流程<select value={targetStage} onChange={(event) => setTargetStage(event.target.value as BambooStage)}><option value="SORT">分选</option><option value="DIPPING">浸胶</option><option value="DRYING">干燥</option></select></label>
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
          <h3>主管选择性回退</h3>
          {(summary?.corrections ?? []).filter((item) => item.status === "OPEN").map((item) => <div className="error-banner" key={item.case_id}>财务要求纠错：{item.reason}</div>)}
          <p>只勾选确实需要重写的工序，系统会自动作废其下游签字，旧版本仍保留用于审计。</p>
          <div className="bamboo-return-options">
            {(["SORT", "DIPPING", "DRYING"] as BambooStage[]).map((stage) => (
              <label key={stage}><input type="checkbox" checked={returnStages.includes(stage)} onChange={(event) => setReturnStages(event.target.checked ? [...returnStages, stage] : returnStages.filter((item) => item !== stage))} />{stage === "SORT" ? "分选" : stage === "DIPPING" ? "浸胶" : "干燥"}</label>
            ))}
          </div>
          <label>回退原因<textarea value={returnReason} onChange={(event) => setReturnReason(event.target.value)} /></label>
          <button disabled={busy || returnStages.length === 0 || !returnReason} onClick={() => void run(() => mobileApiClient.returnBambooRecord(record.record_id, returnStages, returnReason), "已按选择回退")}>确认回退</button>
        </section>
      )}

      {role === "FINANCE_APPROVER" && (
        <section className="bamboo-sheet-section bamboo-operations-panel">
          <h3>财务逐条审批</h3>
          {financeItems.map((item) => (
            <article className="bamboo-operation-card" key={item.item_id}>
              <strong>{item.employee_code} · ¥{item.amount}</strong><span>{item.status}</span>
              <div className="bamboo-inline-actions">
                <button disabled={busy} onClick={() => void run(() => mobileApiClient.decideBambooFinanceItem(item.item_id, "APPROVED", "核对通过"), "条目已批准")}>批准</button>
                <button disabled={busy} onClick={() => void run(() => mobileApiClient.decideBambooFinanceItem(item.item_id, "HELD", "等待厂长说明"), "条目已暂缓")}>暂缓</button>
                <button disabled={busy} onClick={() => void run(() => mobileApiClient.decideBambooFinanceItem(item.item_id, "CORRECTION_REQUIRED", "退回主管判断需重写环节"), "已建立纠错单")}>要求纠错</button>
                <button disabled={busy || !financeNote} onClick={() => void run(() => mobileApiClient.createBambooFinanceInquiry(item.item_id, `询问表单 ${record.display_no}`, financeNote), "询问已发送给厂长")}>询问厂长</button>
              </div>
            </article>
          ))}
          <textarea placeholder="填写暂缓原因或需要厂长说明的问题" value={financeNote} onChange={(event) => setFinanceNote(event.target.value)} />
          <a className="bamboo-export-link" href="/api/v1/mobile/bamboo/finance/export.xlsx">导出单日审计 XLSX</a>
        </section>
      )}

      {WORKER_ROLES.includes(role) && (
        <section className="bamboo-sheet-section bamboo-operations-panel">
          <h3>申请切换职务</h3>
          <select value={newRole} onChange={(event) => setNewRole(event.target.value)}><option value="">请选择</option>{WORKER_ROLES.filter((item) => item !== role).map((item) => <option value={item} key={item}>{item}</option>)}</select>
          <textarea placeholder="申请原因" value={roleReason} onChange={(event) => setRoleReason(event.target.value)} />
          <button disabled={busy || !newRole || !roleReason} onClick={() => void run(() => mobileApiClient.requestBambooRoleChange(newRole, roleReason), "申请已提交，等待厂长同意")}>提交换岗申请</button>
        </section>
      )}

      {role === "PLANT_MANAGER" && roleChanges.some((item) => item.status === "PENDING") && (
        <section className="bamboo-sheet-section bamboo-operations-panel">
          <h3>待审批职务申请</h3>
          {roleChanges.filter((item) => item.status === "PENDING").map((item) => <article className="bamboo-operation-card" key={item.request_id}><strong>{item.employee_code}：{item.from_role} → {item.to_role}</strong><p>{item.reason}</p><div className="bamboo-inline-actions"><button onClick={() => void run(() => mobileApiClient.decideBambooRoleChange(item.request_id, true, "厂长同意"), "职务已切换")}>同意</button><button onClick={() => void run(() => mobileApiClient.decideBambooRoleChange(item.request_id, false, "厂长驳回"), "申请已驳回")}>驳回</button></div></article>)}
        </section>
      )}

      {role === "PLANT_MANAGER" && (
        <section className="bamboo-sheet-section bamboo-operations-panel">
          <h3>人员与工资规则配置</h3>
          <p>新员工先建立档案，再由厂长分配本厂主管、检测人或生产工人职务。</p>
          <input placeholder="员工工号" value={employeeCode} onChange={(event) => setEmployeeCode(event.target.value)} />
          <select value={assignmentRole} onChange={(event) => setAssignmentRole(event.target.value)}><option value="">选择职务</option><option value="SUPERVISOR">主管</option><option value="INSPECTOR">检测人</option><option value="SORT_OPERATOR">分选工</option><option value="DIPPING_OPERATOR">浸胶工</option><option value="DRYING_RACK_OPERATOR">干燥工</option></select>
          <button disabled={busy || !employeeCode || !assignmentRole} onClick={() => void run(() => mobileApiClient.assignBambooEmployeeRole(employeeCode, assignmentRole), "职务已分配")}>分配职务</button>
          <label>分选单位工资<input inputMode="decimal" value={sortRate} onChange={(event) => setSortRate(event.target.value)} /></label>
          <button disabled={busy || !sortRate} onClick={() => void run(() => mobileApiClient.createBambooPayrollRule("SORT", { unit_rate: sortRate, length_multipliers: { "2.1": "5", "2.3": "6", "2.5": "7" } }), "本厂工资规则新版本已生效")}>发布本厂工资规则新版本</button>
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
