import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { acknowledgePlantNotification, listPlantNotifications } from "./api";
import type { ManagementNotification } from "./types";
import "./managed-forms.css";

/** Convert a mobile URL to a web route if possible. */
function resolveLink(item: ManagementNotification): string | null {
  const raw = item.link;
  if (!raw) return null;
  // Mobile deep-link patterns
  if (raw.startsWith("bamboo://") || raw.startsWith("bamboo-app://")) {
    const recordId = item.payload?.record_id as string | undefined;
    if (recordId) return `/plant/production/${encodeURIComponent(recordId)}`;
    return null;
  }
  return raw;
}

export function PlantNotificationsPage() {
  const [items, setItems] = useState<ManagementNotification[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    setError("");
    listPlantNotifications()
      .then((result) => { setItems(result.items); setLoading(false); })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "通知加载失败");
        setLoading(false);
      });
  }
  useEffect(load, []);

  async function acknowledge(item: ManagementNotification) {
    try {
      const updated = await acknowledgePlantNotification(item.notification_id);
      setItems((current) => current.map((value) => (
        value.notification_id === updated.notification_id ? updated : value
      )));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "知悉失败");
    }
  }

  return (
    <section className="managed-forms-page">
      <header className="managed-page-heading">
        <div><h1>消息中心</h1><p>与移动业务共用同一通知和已读状态。</p></div>
      </header>
      {loading && <div role="status">正在加载通知…</div>}
      {error && (
        <div role="alert" className="error-banner">
          {error}{" "}
          <button type="button" onClick={load}>重试</button>
        </div>
      )}
      {!loading && !error && items.length === 0 && (
        <p>当前没有通知。</p>
      )}
      {!loading && !error && items.length > 0 && (
        <div className="managed-form-list">
          {items.map((item) => {
            const webLink = resolveLink(item);
            return (
              <article key={item.notification_id} className="managed-form-card">
                <h2>{item.title}</h2>
                <p>{item.body}</p>
                <p className="signature-muted">
                  {item.created_at ? new Date(item.created_at).toLocaleString() : ""}
                  {" · "}
                  {item.read_at ? "已知悉" : "未读"}
                </p>
                {webLink && (
                  <Link to={webLink}>查看详情</Link>
                )}
                {item.read_at
                  ? <span className="managed-status">已知悉</span>
                  : <button type="button" onClick={() => void acknowledge(item)}>确认知悉</button>}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
