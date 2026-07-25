import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { MobileApiError, mobileApiClient, type BambooRecord, type BambooStage } from "@form-detection/api-client";
import { useMobileSession } from "../session/MobileSessionProvider";
import { BambooOperationsPanel } from "./BambooOperationsPanel";
import { BambooStageForm } from "./BambooStageForm";

type FlowStep = { key: string; stage: BambooStage | null; label: string };

const SORTING_FLOW: FlowStep[] = [
  { key: "sort", stage: "SORT", label: "分选签字" },
  { key: "supervisor", stage: "SUPERVISOR", label: "主管审核" },
  { key: "plant", stage: "PLANT_AUDIT", label: "厂长确认" },
  { key: "effective", stage: null, label: "已生效" },
];
const JOINT_FLOW: FlowStep[] = [
  { key: "dipping", stage: "DIPPING", label: "浸胶记录" },
  { key: "drying", stage: "DRYING", label: "干燥联合签字" },
  { key: "supervisor", stage: "SUPERVISOR", label: "主管审核" },
  { key: "plant", stage: "PLANT_AUDIT", label: "厂长确认" },
  { key: "effective", stage: null, label: "已生效" },
];
const ROLE_STAGE: Record<string, BambooStage> = { SORT_OPERATOR: "SORT", DIPPING_OPERATOR: "DIPPING", DRYING_RACK_OPERATOR: "DRYING", SUPERVISOR: "SUPERVISOR", PLANT_MANAGER: "PLANT_AUDIT" };

export function BambooRecordDetailPage({ recordId }: { recordId: string }) {
  const { sessionMetadata: session } = useMobileSession();
  const [record, setRecord] = useState<BambooRecord | null>(null);
  const [inspectionBlocked, setInspectionBlocked] = useState(true);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setRecord(await mobileApiClient.getBambooRecord(recordId));
    } catch (cause) {
      setError(cause instanceof MobileApiError ? cause.problem.detail : "无法加载竹丝工序记录。");
    } finally {
      setLoading(false);
    }
  }, [recordId]);
  useEffect(() => { void load(); }, [load]);

  const flow = useMemo(
    () => record?.form_type === "DIPPING_DRYING" ? JOINT_FLOW : SORTING_FLOW,
    [record?.form_type],
  );

  if (loading) return <div className="mobile-page"><div className="mobile-loading">加载记录中…</div></div>;
  if (!record) return <div className="mobile-page"><div className="error-banner" role="alert">{error || "记录不可见"}</div></div>;

  const currentIndex = record.status === "COMPLETED"
    ? flow.length - 1
    : flow.findIndex((item) => item.stage === record.current_stage);
  const canSign = record.current_stage !== null && ROLE_STAGE[session?.bamboo_role ?? ""] === record.current_stage;
  const effectiveSubmissionIds = effectiveSubmissions(record, flow);
  const effectiveSubs = record.submissions.filter(s => effectiveSubmissionIds.has(s.submission_id));
  const invalidatedSubs = record.submissions.filter(s => !effectiveSubmissionIds.has(s.submission_id));

  return <div className="mobile-page bamboo-v3-page bamboo-detail-page">
    <header className="bamboo-v3-page-header bamboo-v3-detail-heading">
      <Link to="/mobile/work" aria-label="返回工作列表">‹</Link>
      <div><p>{formTypeLabel(record)} · 查看整张电子表单</p><h2>{record.form_type === "DIPPING_DRYING" ? "《配片数计量考核表》" : "《竹丝装笼跟踪牌》"}</h2></div>
    </header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <section className="bamboo-record-hero">
      <div><span>表单编号</span><strong>{record.display_no}</strong><small>第 {record.revision} 版</small></div>
      <em>{record.status === "COMPLETED" ? "已生效" : stageState(record)}</em>
    </section>

    {record.form_type === "DIPPING_DRYING" && <SourceCard record={record} />}

    <ol className={`bamboo-flow-strip bamboo-flow-${flow.length}`} aria-label={`${formTypeLabel(record)}表内进度`}>
      {flow.map((item, index) => {
        const state = index < currentIndex || (record.status === "COMPLETED" && index === currentIndex)
          ? "done"
          : index === currentIndex ? "current" : "locked";
        return <li key={item.key} className={state}>
          <i aria-hidden="true">{state === "done" ? "✓" : index + 1}</i>
          <span>{item.label}</span>
          <small>{state === "done" ? (item.stage ? "已签字" : "工资已生效") : state === "current" ? "当前步骤" : "尚未开放"}</small>
        </li>;
      })}
    </ol>

    <section className="bamboo-sheet-section bamboo-v3-whole-form">
      <div className="bamboo-section-title"><h3>基础与复用字段</h3><span>{formTypeLabel(record)}</span></div>
      <dl className="bamboo-sheet-grid">
        {Object.entries(record.base_info).map(([key, value]) => <div key={key}><dt>{baseLabel(key)}</dt><dd>{formatValue(value)}</dd></div>)}
      </dl>
    </section>

    <section className="bamboo-sheet-section bamboo-submission-history">
      <div className="bamboo-section-title"><h3>提交与签字记录</h3><span>有效与失效版本全部保留</span></div>
      {record.submissions.length === 0 ? <p className="bamboo-v3-empty-copy">尚无提交记录</p> : <>
        {effectiveSubs.map((submission) => <article className="bamboo-submission-detail effective" key={submission.submission_id}>
          <header>
            <div><strong>{stageLabel(submission.stage)} · 第 {submission.version} 次提交</strong><span>{submission.actor_name}（{roleLabel(submission.role_code)}）</span></div>
            <em>当前有效</em>
          </header>
          <time dateTime={submission.submitted_at ?? undefined}>{submission.submitted_at ? formatTime(submission.submitted_at) : "服务器签字时间待同步"}</time>
          <dl className="bamboo-sheet-grid">
            {Object.entries(submission.values).map(([key, value]) => <div key={key}><dt>{valueLabel(key)}</dt><dd>{formatValue(value)}</dd></div>)}
          </dl>
        </article>)}
        {invalidatedSubs.length > 0 && <details className="bamboo-invalidated-history">
          <summary>历史/已失效（{invalidatedSubs.length} 条）</summary>
          {invalidatedSubs.map((submission) => <article className="bamboo-submission-detail invalidated" key={submission.submission_id}>
            <header>
              <div><strong>{stageLabel(submission.stage)} · 第 {submission.version} 次提交</strong><span>{submission.actor_name}（{roleLabel(submission.role_code)}）</span></div>
              <em>历史/已失效</em>
            </header>
            <time dateTime={submission.submitted_at ?? undefined}>{submission.submitted_at ? formatTime(submission.submitted_at) : "服务器签字时间待同步"}</time>
            <dl className="bamboo-sheet-grid">
              {Object.entries(submission.values).map(([key, value]) => <div key={key}><dt>{valueLabel(key)}</dt><dd>{formatValue(value)}</dd></div>)}
            </dl>
          </article>)}
        </details>}
      </>}
    </section>

    {!canSign && (
      <div className="banner info bamboo-readonly-banner">
        {session?.bamboo_role === "INSPECTOR"
          ? "生产信息仅供核对，请在下方记录检测结果。"
          : "当前记录以只读方式显示；你没有修改此工序的权限。"}
      </div>
    )}
    <BambooOperationsPanel record={record} role={session?.bamboo_role ?? ""} onRefresh={load} onInspectionGateChange={setInspectionBlocked} />
    {canSign && record.current_stage && !(record.current_stage === "PLANT_AUDIT" && inspectionBlocked) && <BambooStageForm record={record} stage={record.current_stage} onSigned={setRecord} />}
  </div>;
}

function SourceCard({ record }: { record: BambooRecord }) {
  const snapshot = record.source_snapshot;
  const upstream = record.upstream_record;
  const sourceBase = upstream?.base_info ?? (isObject(snapshot.base_info) ? snapshot.base_info : {});
  const changed = snapshot.source_status === "UPSTREAM_CHANGED";
  return <section className={`bamboo-source-card${changed ? " changed" : ""}`}>
    <div className="bamboo-section-title"><h3>来源：《竹丝装笼跟踪牌》</h3><span>只读上游记录</span></div>
    {changed && <div className="banner danger" role="alert">上游数据已变更，待主管确认</div>}
    <p><strong>{String(upstream?.display_no ?? snapshot.display_no ?? record.source_ref ?? "—")}</strong> · 第 {String(upstream?.revision ?? snapshot.revision ?? "—")} 版</p>
    <details open>
      <summary>完整上游表单</summary>
      <dl className="bamboo-sheet-grid">
        {Object.entries(sourceBase).map(([key, value]) => <div key={key}><dt>{baseLabel(key)}</dt><dd>{formatValue(value)}</dd></div>)}
      </dl>
      {upstream?.submissions.map((submission) => <article className="bamboo-upstream-submission" key={submission.submission_id}>
        <header><strong>{stageLabel(submission.stage)}</strong><span>{submission.actor_name}（{roleLabel(submission.role_code)}）</span></header>
        <dl className="bamboo-sheet-grid">
          {Object.entries(submission.values).map(([key, value]) => <div key={key}><dt>{valueLabel(key)}</dt><dd>{formatValue(value)}</dd></div>)}
        </dl>
      </article>)}
    </details>
  </section>;
}

function effectiveSubmissions(record: BambooRecord, flow: FlowStep[]): Set<string> {
  const effectiveStages = new Set(
    flow
      .slice(0, record.status === "COMPLETED" ? flow.length : Math.max(0, flow.findIndex((item) => item.stage === record.current_stage)))
      .map((item) => item.stage)
      .filter((stage): stage is BambooStage => stage !== null),
  );
  const latest = new Map<BambooStage, BambooRecord["submissions"][number]>();
  for (const submission of record.submissions) {
    const previous = latest.get(submission.stage);
    if (!previous || submission.version > previous.version) latest.set(submission.stage, submission);
  }
  return new Set([...latest.entries()].filter(([stage]) => effectiveStages.has(stage)).map(([, submission]) => submission.submission_id));
}

function stageState(record: BambooRecord): string {
  if (record.form_type === "DIPPING_DRYING" && record.current_stage === "SUPERVISOR") return "联合作业已完成 · 待主管审核";
  if (record.current_stage === "SUPERVISOR") return "分选已完成 · 待主管审核";
  if (record.current_stage === "PLANT_AUDIT") return "待厂长确认";
  return stageLabel(record.current_stage);
}
function formTypeLabel(record: BambooRecord): string { return record.form_type === "DIPPING_DRYING" ? "《配片数计量考核表》" : "《竹丝装笼跟踪牌》"; }
function stageLabel(stage: BambooStage | null): string { return ({ SORT: "分选", DIPPING: "浸胶", DRYING: "干燥", SUPERVISOR: "主管审核", PLANT_AUDIT: "厂长确认" } as Record<string, string>)[stage ?? ""] ?? "已生效"; }
function roleLabel(role: string): string { return ({ SORT_OPERATOR: "分选工", DIPPING_OPERATOR: "浸胶工", DRYING_RACK_OPERATOR: "干燥工", SUPERVISOR: "主管", PLANT_MANAGER: "厂长" } as Record<string, string>)[role] ?? role; }
function baseLabel(key: string): string { return ({ mode: "作业模式", special_classes: "特殊类", cage_no: "竹笼号", length: "长度", shade: "深浅", grade: "品级", supplier: "供应商", bundle_count: "把数", net_weight: "净重", options_version: "预设版本" } as Record<string, string>)[key] ?? key; }
function valueLabel(key: string): string { return ({ moisture: "含水率检测点", sort_quantity: "分选数量", wage_amount: "工资金额", note: "备注/评价", glue_batch: "胶液批次", glue_before_weight: "胶前重", glue_after_weight: "胶后重", glue_gain: "上胶量", rack_numbers: "干燥架号", rack_count: "架数", conclusion: "审核结论", started_at: "开始时间", ended_at: "结束时间" } as Record<string, string>)[key] ?? key; }
function formatValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(formatValue).join("、") || "—";
  if (isObject(value)) return Object.entries(value).map(([key, item]) => `${baseLabel(key)}：${formatValue(item)}`).join("；") || "—";
  return String(value ?? "—");
}
function isObject(value: unknown): value is Record<string, unknown> { return typeof value === "object" && value !== null && !Array.isArray(value); }
function formatTime(value: string): string { return new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" }).format(new Date(value)); }
