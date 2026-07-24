import { useEffect, useState } from "react";

import {
  decidePlantInspectionAppeal,
  getPlantExceptions,
  terminatePlantInspection,
} from "./api";
import type { BambooInspectionQueueItem } from "./types";
import "./ledger-pages.css";

const STATUS_LABELS: Record<string, string> = {
  OPEN: "等待检测",
  CLAIMED: "检测中",
  EXPIRED: "已过期",
  APPEAL_SUBMITTED: "上诉待审批",
  APPEAL_APPROVED: "上诉已批准",
  APPEAL_REJECTED: "上诉已驳回",
  COMPLETED: "检测完成",
  EARLY_TERMINATED: "厂长提前结束",
};

type Bucket = "active" | "history";

export function PlantExceptionsPage() {
  const [items, setItems] = useState<BambooInspectionQueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [query, setQuery] = useState("");
  const [bucket, setBucket] = useState<Bucket>("active");
  const [error, setError] = useState("");

  // 上诉决定用独立备注
  const [appealNote, setAppealNote] = useState("");
  const [terminateRecordId, setTerminateRecordId] = useState("");
  const [terminateReason, setTerminateReason] = useState("");

  function reload() {
    setLoading(true);
    setError("");
    void getPlantExceptions(bucket, query).then((result) => {
      setItems(result.items);
      setLoading(false);
    }).catch((cause: unknown) => {
      setError(cause instanceof Error ? cause.message : "检测队列加载失败");
      setLoading(false);
    });
  }
  useEffect(reload, [bucket]);

  async function decide(recordId: string, approve: boolean) {
    try {
      await decidePlantInspectionAppeal(
        recordId,
        approve,
        approve
          ? (appealNote || "厂长批准上诉")
          : (appealNote || "厂长驳回上诉"),
      );
      setAppealNote("");
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "审批失败");
    }
  }

  async function handleTerminate(recordId: string) {
    if (!terminateReason.trim()) return;
    try {
      await terminatePlantInspection(recordId, crypto.randomUUID(), terminateReason);
      setTerminateRecordId("");
      setTerminateReason("");
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "终止检测失败");
    }
  }

  return (
    <section className="ledger-page">
      <header>
        <h1>检测异常与上诉</h1>
        <p>查看检测窗口状态及 24 小时上诉结果。可提前终止检测、审批上诉。</p>
      </header>
      {error && <div role="alert">{error}</div>}
      {loading && <div role="status">正在加载检测队列…</div>}

      {/* 筛选栏 */}
      <div className="ledger-filters">
        <label>
          搜索表号或笼号
          <input
            type="search"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="输入表号或笼号…"
          />
        </label>
        <label>
          范围
          <select value={bucket} onChange={(event) => setBucket(event.target.value as Bucket)}>
            <option value="active">当前处理</option>
            <option value="history">历史记录</option>
          </select>
        </label>
        <button type="button" onClick={reload}>搜索</button>
      </div>

      {/* 列表 */}
      <div className="ledger-case-list">
        {!loading && items.length === 0 && !error && (
          <div className="ledger-empty">
            <p><strong>当前没有检测待办事项。</strong></p>
            <p className="signature-muted">
              检测窗口在生产记录进入 PLANT_AUDIT 环节后自动开启。
              检测员完成检测后，窗口将关闭或进入上诉阶段。
            </p>
          </div>
        )}
        {items.map((item) => (
          <article key={item.record_id} className="ledger-exception-item">
            <header>
              <strong>{item.display_no} · 笼号 {item.cage_no || "无笼号"}</strong>
              <span className={`ledger-tag ${item.status === "APPEAL_SUBMITTED" ? "ledger-tag-alert" : ""}`}>
                {STATUS_LABELS[item.status] ?? item.status}
              </span>
            </header>
            <p className="signature-muted">
              截止时间：{item.deadline_at
                ? new Date(item.deadline_at).toLocaleString()
                : "—"}
              {item.appeal_deadline_at && ` · 上诉截止：${new Date(item.appeal_deadline_at).toLocaleString()}`}
            </p>

            {/* 可终止的检测 */}
            {["OPEN", "CLAIMED"].includes(item.status) && (
              <div className="ledger-exception-actions">
                {terminateRecordId === item.record_id ? (
                  <div className="ledger-inline-form">
                    <textarea
                      aria-label="终止原因"
                      value={terminateReason}
                      onChange={(event) => setTerminateReason(event.target.value)}
                      placeholder="请填写终止原因（必填）"
                    />
                    <div className="ledger-inline-actions">
                      <button
                        type="button"
                        disabled={!terminateReason.trim()}
                        onClick={() => void handleTerminate(item.record_id)}
                      >
                        确认终止
                      </button>
                      <button type="button" className="secondary-button" onClick={() => {
                        setTerminateRecordId("");
                        setTerminateReason("");
                      }}>取消</button>
                    </div>
                  </div>
                ) : (
                  <button type="button" className="secondary-button" onClick={() => setTerminateRecordId(item.record_id)}>
                    终止检测窗口
                  </button>
                )}
              </div>
            )}

            {/* 上诉处理 */}
            {item.status === "APPEAL_SUBMITTED" && item.appeal_payload && (
              <div className="ledger-exception-appeal">
                <h4>上诉理由</h4>
                {item.appeal_payload.target_stage && (
                  <p>目标环节：{item.appeal_payload.target_stage}</p>
                )}
                <blockquote className="signature-appeal-quote">
                  {item.appeal_payload.text_evidence || "未提供上诉证据"}
                </blockquote>
                <textarea
                  aria-label="上诉审批意见"
                  value={appealNote}
                  onChange={(event) => setAppealNote(event.target.value)}
                  placeholder="审批意见（可选）"
                />
                <p className="signature-muted">批准后系统将把记录打回对应生产环节重新检测。</p>
                <div className="ledger-inline-actions">
                  <button type="button" onClick={() => void decide(item.record_id, true)}>
                    批准并打回重检
                  </button>
                  <button type="button" onClick={() => void decide(item.record_id, false)}>
                    驳回上诉
                  </button>
                </div>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
