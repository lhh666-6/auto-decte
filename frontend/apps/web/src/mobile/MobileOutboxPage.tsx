import { useCallback, useEffect, useState } from "react";

import { useMobileSession } from "./session/MobileSessionProvider";
import { listAll, remove, resetPending, type OutboxEntry } from "./storage/outbox";
import { flushPendingOutbox } from "./sync/SubmissionCoordinator";

const STATUS_LABELS: Record<OutboxEntry["status"], string> = {
  PENDING: "等待同步",
  SUBMITTING: "同步中",
  FAILED_RETRYABLE: "稍后重试",
  FAILED_FINAL: "需要处理",
};

export function MobileOutboxPage() {
  const { sessionMetadata } = useMobileSession();
  const [items, setItems] = useState<OutboxEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await listAll(sessionMetadata?.employee_code));
      setError("");
    } catch {
      setError("无法读取待同步记录，请重试。");
    } finally {
      setLoading(false);
    }
  }, [sessionMetadata?.employee_code]);

  useEffect(() => { void load(); }, [load]);

  const retry = async (outboxId: string) => {
    try {
      await resetPending(outboxId);
      await flushPendingOutbox(sessionMetadata?.employee_code);
      await load();
    } catch {
      setError("重试失败，记录仍保留在本机。");
    }
  };

  const discard = async (outboxId: string) => {
    if (!window.confirm("这条记录尚未成功提交。确认永久删除吗？")) return;
    try {
      await remove(outboxId);
      await load();
    } catch {
      setError("删除未提交记录失败，请重试。");
    }
  };

  const syncing = items.some((item) => item.status === "SUBMITTING");
  return (
    <div className="mobile-page">
      <header className="mobile-page-header"><h2>待同步</h2>{syncing && <span className="status-pill warning">同步中…</span>}</header>
      {error && <div className="error-banner" role="alert"><p>{error}</p><button type="button" onClick={() => void load()}>重试读取</button></div>}
      {loading ? (
        <div className="mobile-loading">加载中…</div>
      ) : items.length === 0 ? (
        <div className="mobile-empty"><p>所有记录已同步</p><small>断网时填写的记录会出现在这里</small></div>
      ) : (
        <ul className="mobile-outbox-list">
          {items.map((item) => (
            <li key={item.outboxId} className="mobile-outbox-card">
              <strong>{String(item.payload.form_type ?? "电子表单")}</strong>
              <span>{STATUS_LABELS[item.status]} · 尝试 {item.attemptCount} 次</span>
              <small>{new Date(item.createdAt).toLocaleString("zh-CN")}</small>
              {item.lastError && <p role="alert">{item.lastError}</p>}
              {item.lastRequestId && <small>请求编号：{item.lastRequestId}</small>}
              <div className="mobile-form-actions">
                <button type="button" onClick={() => void retry(item.outboxId)}>重试</button>
                <button type="button" onClick={() => void discard(item.outboxId)}>删除未提交记录</button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
