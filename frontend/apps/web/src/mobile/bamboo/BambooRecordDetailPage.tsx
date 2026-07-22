import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { MobileApiError, mobileApiClient, type BambooRecord, type BambooStage } from "@form-detection/api-client";
import { useMobileSession } from "../session/MobileSessionProvider";
import { BambooOperationsPanel } from "./BambooOperationsPanel";
import { BambooStageForm } from "./BambooStageForm";

const FLOW: Array<{ stage: BambooStage; label: string }> = [
  { stage: "SORT", label: "分选" }, { stage: "DIPPING", label: "浸胶" }, { stage: "DRYING", label: "干燥" }, { stage: "SUPERVISOR", label: "主管审核" }, { stage: "PLANT_AUDIT", label: "厂长审核" },
];
const ROLE_STAGE: Record<string, BambooStage> = { SORT_OPERATOR: "SORT", DIPPING_OPERATOR: "DIPPING", DRYING_RACK_OPERATOR: "DRYING", SUPERVISOR: "SUPERVISOR", PLANT_MANAGER: "PLANT_AUDIT" };

export function BambooRecordDetailPage({ recordId }: { recordId: string }) {
  const { sessionMetadata: session } = useMobileSession();
  const [record, setRecord] = useState<BambooRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true); setError("");
    try { setRecord(await mobileApiClient.getBambooRecord(recordId)); }
    catch (cause) { setError(cause instanceof MobileApiError ? cause.problem.detail : "无法加载竹丝工序记录。"); }
    finally { setLoading(false); }
  }, [recordId]);
  useEffect(() => { void load(); }, [load]);
  if (loading) return <div className="mobile-page"><div className="mobile-loading">加载记录中…</div></div>;
  if (!record) return <div className="mobile-page"><div className="error-banner" role="alert">{error || "记录不可见"}</div></div>;

  const completed = new Set(record.submissions.map((item) => item.stage));
  const currentIndex = record.current_stage ? FLOW.findIndex((item) => item.stage === record.current_stage) : FLOW.length;
  const canSign = record.current_stage !== null && ROLE_STAGE[session?.bamboo_role ?? ""] === record.current_stage;
  const sort = record.submissions.find((item) => item.stage === "SORT");
  const dippingDrying = record.submissions.filter((item) => item.stage === "DIPPING" || item.stage === "DRYING");
  const reviews = record.submissions.filter((item) => item.stage === "SUPERVISOR" || item.stage === "PLANT_AUDIT");

  return <div className="mobile-page bamboo-v3-page bamboo-detail-page">
    <header className="bamboo-v3-page-header bamboo-v3-detail-heading"><Link to="/mobile/work" aria-label="返回工作列表">‹</Link><div><p>查看并记录当前工序</p><h2>竹丝流程详情</h2></div></header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <section className="bamboo-record-hero"><div><span>记录编号</span><strong>{record.display_no}</strong></div><em>{record.status === "COMPLETED" ? "已完成" : stageState(record.current_stage)}</em></section>
    <ol className="bamboo-flow-strip" aria-label="工序进度">{FLOW.map((item, index) => {
      const state = completed.has(item.stage) ? "done" : index === currentIndex ? "current" : index > currentIndex ? "locked" : "";
      return <li key={item.stage} className={state}><i aria-hidden="true">{completed.has(item.stage) ? "✓" : index + 1}</i><span>{item.label}</span><small>{state === "done" ? "已签字" : state === "current" ? "已开放" : "前序完成后开放"}</small></li>;
    })}</ol>

    <section className="bamboo-sheet-section bamboo-v3-whole-form"><div className="bamboo-section-title"><h3>整张电子表单</h3><span>第 {record.revision} 版</span></div><dl className="bamboo-sheet-grid">{Object.entries(record.base_info).map(([key, value]) => <div key={key}><dt>{baseLabel(key)}</dt><dd>{String(value ?? "—")}</dd></div>)}</dl></section>
    {sort && <SubmissionSection title="分选记录" submissions={[sort]} footer="分选签字后工资已确定" />}
    {dippingDrying.length > 0 && <SubmissionSection title="浸胶与干燥联合作业" submissions={dippingDrying} footer={dippingDrying.length === 2 ? "两道工序已组合确认，联合工资待厂长审核生效" : "等待干燥完成后一起签字确认"} />}
    {reviews.map((submission) => <SubmissionSection key={submission.submission_id} title={`${stageLabel(submission.stage)}记录`} submissions={[submission]} />)}
    <BambooOperationsPanel record={record} role={session?.bamboo_role ?? ""} onRefresh={load} />
    {canSign && record.current_stage && <BambooStageForm record={record} stage={record.current_stage} onSigned={setRecord} />}
  </div>;
}

function SubmissionSection({ title, submissions, footer }: { title: string; submissions: BambooRecord["submissions"]; footer?: string }) {
  return <section className="bamboo-sheet-section"><div className="bamboo-section-title"><h3>{title}</h3><span>{submissions.map((item) => item.actor_name).join(" · ")} 已签字</span></div>{submissions.map((submission) => <dl className="bamboo-sheet-grid" key={submission.submission_id}>{Object.entries(submission.values).map(([key, value]) => <div key={key}><dt>{valueLabel(key)}</dt><dd>{formatValue(value)}</dd></div>)}</dl>)}{footer && <p className="bamboo-v3-form-note">{footer}</p>}</section>;
}
function stageState(stage: BambooStage | null): string { return stage ? `进行中 · ${stageLabel(stage)}` : "流程完成"; }
function stageLabel(stage: BambooStage): string { return ({ SORT: "分选", DIPPING: "浸胶", DRYING: "干燥", SUPERVISOR: "主管审核", PLANT_AUDIT: "厂长审核" })[stage]; }
function baseLabel(key: string): string { return ({ cage_no: "竹笼号", length: "长度", grade: "等级", bundle_count: "捆数" } as Record<string, string>)[key] ?? key; }
function valueLabel(key: string): string { return ({ moisture: "含水率检测点", sort_quantity: "分选数量", wage_amount: "工资金额", note: "备注", glue_batch: "胶液批次", rack_no: "干燥架号", conclusion: "审核结论" } as Record<string, string>)[key] ?? key; }
function formatValue(value: unknown): string { return Array.isArray(value) ? value.join("、") : String(value ?? "—"); }
