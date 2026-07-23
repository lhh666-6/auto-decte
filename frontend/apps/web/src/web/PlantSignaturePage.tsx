import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import {
  auditPlantRecord,
  decidePlantInspectionAppeal,
  getPlantProductionDetail,
  returnPlantRecord,
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
  PLANT_AUDIT: "厂长签字",
};

function readable(value: unknown): string {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

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

function stageOptions(detail: BambooProductionDetail): Array<[string, string]> {
  return detail.form_type === "SORTING"
    ? [["SORT", "分选"]]
    : [["DIPPING", "浸胶"], ["DRYING", "干燥"]];
}

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
  const [returnOpen, setReturnOpen] = useState(false);
  const [returnStages, setReturnStages] = useState<string[]>([]);
  const [returnReason, setReturnReason] = useState("");

  async function reload() {
    if (!recordId) return;
    try {
      setDetail(await getPlantProductionDetail(recordId));
      setError("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "生产记录加载失败");
    }
  }

  useEffect(() => {
    void reload();
  }, [recordId]);

  const activeStages = useMemo(
    () => detail ? stageOptions(detail) : [],
    [detail],
  );

  async function run(action: () => Promise<unknown>): Promise<boolean> {
    setBusy(true);
    setError("");
    try {
      await action();
      await reload();
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "操作失败");
      return false;
    } finally {
      setBusy(false);
    }
  }

  function openSignatureConfirmation() {
    setSignatureKey(crypto.randomUUID());
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
    if (succeeded) setConfirming(false);
  }

  async function terminateInspection() {
    if (!detail) return;
    if (!window.confirm("停止后检测员将失去当前检测权限，确定提前结束检测吗？")) return;
    await run(() => terminatePlantInspection(detail.record_id, crypto.randomUUID()));
  }

  async function decideAppeal(approve: boolean) {
    if (!detail) return;
    await run(() => decidePlantInspectionAppeal(
      detail.record_id,
      approve,
      appealNote,
    ));
    setAppealNote("");
  }

  async function submitReturn() {
    if (!detail || !returnStages.length || !returnReason.trim()) return;
    await run(() => returnPlantRecord(
      detail.record_id,
      returnStages,
      returnReason,
      detail.revision,
    ));
    setReturnOpen(false);
    setReturnStages([]);
    setReturnReason("");
  }

  if (!detail && !error) return <div role="status">正在加载签字资料…</div>;

  return (
    <section className="plant-signature-page">
      <nav><Link to="/plant/production">← 返回生产看板</Link></nav>
      {error && <div className="signature-alert" role="alert">{error}</div>}
      {detail && (
        <>
          <header className="signature-hero">
            <div>
              <span className="signature-kicker">厂长独立签字页</span>
              <h1>{detail.display_no}</h1>
              <p>笼号 {detail.cage_no || "—"} · 版本 {detail.revision}</p>
            </div>
            <span className="signature-stage">
              {STAGE_LABELS[detail.current_stage ?? ""] ?? detail.current_stage ?? "已完成"}
            </span>
          </header>

          <section className="signature-card">
            <h2>流程进度</h2>
            <ol className="signature-flow">
              {["SORT", "DIPPING", "DRYING", "SUPERVISOR", "PLANT_AUDIT"]
                .filter((stage) => detail.form_type !== "SORTING" || !["DIPPING", "DRYING"].includes(stage))
                .map((stage) => (
                  <li
                    key={stage}
                    className={detail.submissions.some((item) => item.stage === stage && !item.invalidated)
                      ? "is-complete"
                      : detail.current_stage === stage ? "is-current" : ""}
                  >
                    {STAGE_LABELS[stage]}
                  </li>
                ))}
            </ol>
          </section>

          <section className="signature-card">
            <h2>表单基础信息</h2>
            <Fields values={detail.base_info} />
          </section>

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

          <section className="signature-card">
            <h2>本表提交记录</h2>
            <div className="signature-submissions">
              {detail.submissions.map((item) => (
                <SubmissionCard key={item.submission_id} item={item} />
              ))}
              {!detail.submissions.length && <p className="signature-muted">暂无提交记录</p>}
            </div>
          </section>

          <section className="signature-card">
            <h2>检测状态</h2>
            {detail.inspection_window ? (
              <>
                <p>
                  状态：{detail.inspection_window.status}
                  {detail.inspection_window.remaining_seconds > 0
                    ? ` · 剩余约 ${Math.ceil(detail.inspection_window.remaining_seconds / 60)} 分钟`
                    : ""}
                </p>
                {detail.inspections.map((inspection) => (
                  <article className="signature-inspection" key={inspection.inspection_id}>
                    <strong>{inspection.conclusion === "QUALIFIED" ? "检测合格" : inspection.conclusion}</strong>
                    <span>{inspection.actor_name}</span>
                    {inspection.note && <p>{inspection.note}</p>}
                    {inspection.evidence.map((evidence) => (
                      <p key={evidence.asset_id}>
                        检测记录：{evidence.text_content || evidence.file_id || evidence.evidence_type}
                      </p>
                    ))}
                  </article>
                ))}
              </>
            ) : <p className="signature-muted">无检测窗口</p>}

            {["OPEN", "CLAIMED"].includes(detail.inspection_window?.status ?? "") && (
              <button type="button" disabled={busy} onClick={() => void terminateInspection()}>
                停止检测并提前签字
              </button>
            )}

            {detail.inspection_window?.status === "APPEAL_SUBMITTED" && (
              <div className="signature-appeal">
                <h3>检测上诉待审批</h3>
                <p>{detail.inspection_window.appeal_payload?.text_evidence}</p>
                <textarea
                  aria-label="上诉审批意见"
                  value={appealNote}
                  onChange={(event) => setAppealNote(event.target.value)}
                  placeholder="填写审批意见（可选）"
                />
                <div>
                  <button type="button" disabled={busy} onClick={() => void decideAppeal(true)}>同意上诉</button>
                  <button type="button" disabled={busy} onClick={() => void decideAppeal(false)}>驳回上诉</button>
                </div>
              </div>
            )}
          </section>

          <section className="signature-card signature-actions">
            <h2>厂长处理</h2>
            <label>
              签字备注（可选）
              <textarea
                aria-label="签字备注"
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </label>
            {detail.signature_gate.can_sign ? (
              <button type="button" disabled={busy} onClick={openSignatureConfirmation}>
                通过并签字
              </button>
            ) : (
              <p className="signature-warning">
                当前不可签字：{detail.signature_gate.reason || "流程条件尚未满足"}
              </p>
            )}
            <button type="button" className="secondary-button" onClick={() => setReturnOpen((value) => !value)}>
              选择环节打回
            </button>
            {returnOpen && (
              <div className="signature-return">
                {activeStages.map(([value, label]) => (
                  <label key={value}>
                    <input
                      type="checkbox"
                      checked={returnStages.includes(value)}
                      onChange={(event) => setReturnStages((current) => event.target.checked
                        ? [...current, value]
                        : current.filter((item) => item !== value))}
                    />
                    {label}
                  </label>
                ))}
                <textarea
                  aria-label="打回原因"
                  value={returnReason}
                  onChange={(event) => setReturnReason(event.target.value)}
                  placeholder="请填写打回原因"
                />
                <button
                  type="button"
                  disabled={busy || !returnStages.length || !returnReason.trim()}
                  onClick={() => void submitReturn()}
                >
                  确认打回
                </button>
              </div>
            )}
          </section>

          {confirming && (
            <div className="signature-dialog-backdrop" role="presentation">
              <div className="signature-dialog" role="dialog" aria-modal="true" aria-labelledby="signature-dialog-title">
                <h2 id="signature-dialog-title">签字前核对</h2>
                <p>表号：{detail.display_no}</p>
                <p>笼号：{detail.cage_no || "—"}</p>
                <p>签字人：{session?.employee_name || session?.employee_code || "当前厂长"}</p>
                <p>工厂：{session?.factory_name || detail.factory_id}</p>
                <p>记录版本：{detail.revision}</p>
                <div>
                  <button type="button" disabled={busy} onClick={() => void confirmSignature()}>
                    确认签字
                  </button>
                  <button type="button" disabled={busy} onClick={() => setConfirming(false)}>取消</button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}
