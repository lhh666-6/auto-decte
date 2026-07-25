import { useCallback, useEffect, useState } from "react";

import {
  createQualityDisposition,
  decidePlantInspectionAppeal,
  getPlantExceptions,
  getPlantProductionDetail,
  terminatePlantInspection,
  updateQualityDisposition,
} from "./api";
import type {
  BambooInspectionQueueItem,
  BambooProductionDetail,
  QualityDisposition,
} from "./types";
import "./ledger-pages.css";

const STATUS_LABELS: Record<string, string> = {
  OPEN: "等待检测", CLAIMED: "检测中", EXPIRED: "已过期",
  APPEAL_SUBMITTED: "上诉待审批", APPEAL_APPROVED: "上诉已批准",
  APPEAL_REJECTED: "上诉已驳回", COMPLETED: "检测完成",
  EARLY_TERMINATED: "厂长提前结束",
};

const STAGE_LABELS: Record<string, string> = {
  SORT: "分选", DIPPING: "浸胶", DRYING: "干燥",
};

type Bucket = "active" | "history" | "all";

const BUCKET_TABS: Array<{ key: Bucket; label: string }> = [
  { key: "active", label: "待我处理" },
  { key: "history", label: "已处置" },
  { key: "all", label: "全部检测记录" },
];

export function PlantExceptionsPage() {
  const [items, setItems] = useState<BambooInspectionQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [bucket, setBucket] = useState<Bucket>("active");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  // Appeal
  const [appealNote, setAppealNote] = useState("");
  const [terminateRecordId, setTerminateRecordId] = useState("");
  const [terminateReason, setTerminateReason] = useState("");

  // Quality Disposition
  const [dispRecordId, setDispRecordId] = useState("");
  const [dispDetail, setDispDetail] = useState<BambooProductionDetail | null>(null);
  const [dispExisting, setDispExisting] = useState<QualityDisposition | null>(null);
  const [dispStage, setDispStage] = useState("");
  const [dispOrigGrade, setDispOrigGrade] = useState("");
  const [dispEffGrade, setDispEffGrade] = useState("");
  const [dispDecision, setDispDecision] = useState("CONFIRMED");
  const [dispNote, setDispNote] = useState("");
  const [dispSubmitting, setDispSubmitting] = useState(false);
  const [showDisposition, setShowDisposition] = useState(false);

  function reload() {
    setLoading(true); setError("");
    void getPlantExceptions(bucket, query).then((r) => {
      setItems(r.items); setLoading(false);
    }).catch((c: unknown) => {
      setError(c instanceof Error ? c.message : "检测队列加载失败"); setLoading(false);
    });
  }
  useEffect(reload, [bucket]);

  async function decide(recordId: string, approve: boolean) {
    try {
      await decidePlantInspectionAppeal(recordId, approve,
        approve ? (appealNote || "厂长批准上诉") : (appealNote || "厂长驳回上诉"));
      setAppealNote(""); reload();
    } catch (c) { setError(c instanceof Error ? c.message : "审批失败"); }
  }

  async function handleTerminate(recordId: string) {
    if (!terminateReason.trim()) return;
    try {
      await terminatePlantInspection(recordId, crypto.randomUUID(), terminateReason);
      setTerminateRecordId(""); setTerminateReason(""); reload();
    } catch (c) { setError(c instanceof Error ? c.message : "终止检测失败"); }
  }

  // ── Quality Disposition ──────────────────────────────────────

  const openDisposition = useCallback(async (item: BambooInspectionQueueItem) => {
    setDispRecordId(item.record_id);
    setDispDetail(null); setDispExisting(null);
    setDispStage(""); setDispOrigGrade(""); setDispEffGrade("");
    setDispDecision("CONFIRMED"); setDispNote("");
    setShowDisposition(true);
    try {
      const [detail, existing] = await Promise.all([
        getPlantProductionDetail(item.record_id),
        import("./api").then(m => m.getQualityDisposition(item.record_id).catch(() => null)),
      ]);
      setDispDetail(detail);
      setDispExisting(existing);
      // Derive original grade from record base_info
      const bi = detail.base_info as Record<string, unknown> | undefined;
      const og = bi ? String(bi.grade ?? "") : "";
      setDispOrigGrade(og);
      if (existing) {
        setDispStage(existing.responsible_stage);
        setDispEffGrade(existing.effective_grade);
        setDispDecision(existing.decision);
        setDispNote(existing.decision_note || "");
      } else {
        setDispEffGrade(og || "A");
      }
    } catch (c) {
      setError(c instanceof Error ? c.message : "加载记录详情失败");
    }
  }, []);

  async function submitDisposition() {
    if (!dispStage || !dispOrigGrade || !dispEffGrade) {
      setError("请完整填写责任环节、原评级和最终评级"); return;
    }
    setDispSubmitting(true); setError("");
    try {
      if (dispExisting) {
        await updateQualityDisposition(dispRecordId, {
          effective_grade: dispEffGrade,
          decision: dispDecision,
          decision_note: dispNote,
        });
        setMessage("处置已更新");
      } else {
        await createQualityDisposition({
          record_id: dispRecordId,
          inspection_id: dispDetail?.inspections?.[0]?.inspection_id ?? null,
          factory_id: dispDetail?.factory_id ?? "",
          responsible_stage: dispStage,
          original_grade: dispOrigGrade,
          effective_grade: dispEffGrade,
          decision: dispDecision,
          decision_note: dispNote,
        });
        setMessage("质量处置已提交");
      }
      setMessage(dispExisting ? "处置已更新" : "质量处置已提交并签字");
      setShowDisposition(false);
      reload();
    } catch (c) {
      setError(c instanceof Error ? c.message : "处置提交失败");
    } finally { setDispSubmitting(false); }
  }

  // Resolve responsible person from stage submission
  const responsiblePerson = (() => {
    if (!dispStage || !dispDetail) return null;
    const sub = (dispDetail.submissions || []).find(
      (s) => s.stage === dispStage && !s.invalidated,
    );
    return sub ? { name: sub.actor_name, code: sub.actor_id, role: sub.role_code } : null;
  })();

  return (
    <section className="ledger-page">
      <header>
        <h1>检测异常与质量处置</h1>
        <p>查看检测窗口状态，处理上诉，对生产记录作出最终质量评级。</p>
      </header>
      {error && <div role="alert" className="ledger-error">{error}
        <button type="button" onClick={() => setError("")}>✕</button></div>}
      {message && <div role="status" className="ledger-success">{message}
        <button type="button" onClick={() => setMessage("")}>✕</button></div>}
      {loading && <div role="status">正在加载检测队列…</div>}

      <div className="ledger-filters">
        <label>搜索表号或笼号
          <input type="search" value={query}
            onChange={(e) => setQuery(e.target.value)} placeholder="输入表号或笼号…" />
        </label>
        <nav className="tabs" aria-label="质量分类" style={{ marginBottom: 0 }}>
          {BUCKET_TABS.map(b => (
            <button key={b.key} type="button" className={`tab${bucket === b.key ? " on" : ""}`}
              onClick={() => setBucket(b.key)}>{b.label}</button>
          ))}
        </nav>
        <button type="button" onClick={reload} className="secondary-button">搜索</button>
      </div>

      <div className="ledger-case-list">
        {!loading && items.length === 0 && !error && (
          <div className="ledger-empty">
            <p><strong>当前没有检测待办事项。</strong></p>
            <p className="signature-muted">检测窗口在生产记录进入 PLANT_AUDIT 环节后自动开启。</p>
          </div>
        )}
        {items.map((item) => (
          <article key={item.record_id} className="ledger-exception-item">
            <header>
              <strong>{item.display_no} · 笼号 {item.cage_no || "—"}</strong>
              <span className={`ledger-tag ${item.status === "APPEAL_SUBMITTED" ? "ledger-tag-alert" : ""}`}>
                {STATUS_LABELS[item.status] ?? item.status}
              </span>
            </header>
            <p className="signature-muted">
              截止时间：{item.deadline_at ? new Date(item.deadline_at).toLocaleString() : "—"}
              {item.appeal_deadline_at && ` · 上诉截止：${new Date(item.appeal_deadline_at).toLocaleString()}`}
            </p>

            {/* 质量处置按钮 */}
            {["COMPLETED", "EARLY_TERMINATED", "APPEAL_REJECTED"].includes(item.status) && (
              <div className="ledger-exception-actions">
                <button type="button" className="primary-button"
                  onClick={() => void openDisposition(item)}>
                  质量处置
                </button>
              </div>
            )}

            {/* 终止检测 */}
            {["OPEN", "CLAIMED"].includes(item.status) && (
              <div className="ledger-exception-actions">
                {terminateRecordId === item.record_id ? (
                  <div className="ledger-inline-form">
                    <textarea aria-label="终止原因" value={terminateReason}
                      onChange={(e) => setTerminateReason(e.target.value)}
                      placeholder="请填写终止原因（必填）" />
                    <div className="ledger-inline-actions">
                      <button type="button" disabled={!terminateReason.trim()}
                        onClick={() => void handleTerminate(item.record_id)}>确认终止</button>
                      <button type="button" className="secondary-button"
                        onClick={() => { setTerminateRecordId(""); setTerminateReason(""); }}>取消</button>
                    </div>
                  </div>
                ) : (
                  <button type="button" className="secondary-button"
                    onClick={() => setTerminateRecordId(item.record_id)}>终止检测窗口</button>
                )}
              </div>
            )}

            {/* 上诉处理 */}
            {item.status === "APPEAL_SUBMITTED" && item.appeal_payload && (
              <div className="ledger-exception-appeal">
                <h4>上诉理由</h4>
                {item.appeal_payload.target_stage && <p>目标环节：{item.appeal_payload.target_stage}</p>}
                <blockquote className="signature-appeal-quote">
                  {item.appeal_payload.text_evidence || "未提供上诉证据"}
                </blockquote>
                <textarea aria-label="上诉审批意见" value={appealNote}
                  onChange={(e) => setAppealNote(e.target.value)} placeholder="审批意见（可选）" />
                <div className="ledger-inline-actions">
                  <button type="button" onClick={() => void decide(item.record_id, true)}>批准上诉</button>
                  <button type="button" onClick={() => void decide(item.record_id, false)}>驳回上诉</button>
                </div>
              </div>
            )}
          </article>
        ))}
      </div>

      {/* ── Quality Disposition Modal ─────────────────────────── */}
      {showDisposition && (
        <div className="ledger-modal-overlay" onClick={() => setShowDisposition(false)}>
          <div className="ledger-modal" onClick={(e) => e.stopPropagation()}>
            <header>
              <h2>质量处置</h2>
              <button type="button" className="secondary-button"
                onClick={() => setShowDisposition(false)}>✕</button>
            </header>

            {dispDetail ? (
              <div className="disposition-form">
                <div className="disposition-summary">
                  <p><strong>表号：</strong>{dispDetail.display_no}</p>
                  <p><strong>笼号：</strong>{dispDetail.cage_no || "—"}</p>
                  <p><strong>工厂：</strong>{dispDetail.factory_id}</p>
                  <p><strong>当前状态：</strong>{dispDetail.current_stage}</p>
                  {dispExisting && (
                    <p className="signature-muted">已有处置记录（可修订）· 版本 {dispExisting.revision}</p>
                  )}
                </div>

                <label>责任环节
                  <select value={dispStage}
                    onChange={(e) => setDispStage(e.target.value)}>
                    <option value="">— 选择 —</option>
                    {Object.entries(STAGE_LABELS).map(([k, v]) =>
                      <option key={k} value={k}>{v}</option>)}
                  </select>
                </label>

                {responsiblePerson && (
                  <div className="disposition-responsible">
                    <p><strong>责任人员：</strong>{responsiblePerson.name}
                      <span className="signature-muted">（系统自动绑定，不可手输）</span></p>
                    <p className="signature-muted">工号 {responsiblePerson.code} · {responsiblePerson.role}</p>
                  </div>
                )}

                <label>原评级
                  <input type="text" value={dispOrigGrade}
                    onChange={(e) => setDispOrigGrade(e.target.value)}
                    placeholder="来自生产记录" readOnly={!!dispExisting} />
                </label>

                <label>最终评级
                  <select value={dispEffGrade}
                    onChange={(e) => setDispEffGrade(e.target.value)}>
                    <option value="">— 选择 —</option>
                    <option value="A">A</option>
                    <option value="B">B</option>
                  </select>
                </label>

                <label>处置结论
                  <select value={dispDecision}
                    onChange={(e) => setDispDecision(e.target.value)}>
                    <option value="CONFIRMED">确认原评级</option>
                    <option value="DOWNGRADED">调整评级</option>
                  </select>
                </label>

                <label>处置说明
                  <textarea value={dispNote}
                    onChange={(e) => setDispNote(e.target.value)}
                    placeholder="厂长处置说明（必填）" rows={3} />
                </label>

                <div className="ledger-inline-actions">
                  <button type="button" onClick={() => void submitDisposition()}
                    disabled={dispSubmitting || !dispStage || !dispEffGrade}>
                    {dispSubmitting ? "提交中…" : dispExisting ? "更新处置" : "确认处置并签字"}
                  </button>
                  <button type="button" className="secondary-button"
                    onClick={() => setShowDisposition(false)}>取消</button>
                </div>
              </div>
            ) : (
              <div className="ledger-empty"><p>正在加载记录详情…</p></div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
