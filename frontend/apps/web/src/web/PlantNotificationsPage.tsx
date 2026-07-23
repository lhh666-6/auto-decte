import { useEffect, useState } from "react";

import { acknowledgePlantNotification, listPlantNotifications } from "./api";
import type { ManagementNotification } from "./types";
import "./managed-forms.css";

export function PlantNotificationsPage() {
  const [items, setItems] = useState<ManagementNotification[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    listPlantNotifications()
      .then((result) => setItems(result.items))
      .catch((cause: unknown) => setError(
        cause instanceof Error ? cause.message : "通知加载失败",
      ));
  }, []);

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
      {error && <div role="alert" className="error-banner">{error}</div>}
      <div className="managed-form-list">
        {items.map((item) => (
          <article key={item.notification_id} className="managed-form-card">
            <h2>{item.title}</h2>
            <p>{item.body}</p>
            {item.read_at
              ? <span className="managed-status">已知悉</span>
              : <button type="button" onClick={() => void acknowledge(item)}>确认知悉</button>}
          </article>
        ))}
        {!items.length && <p>当前没有通知。</p>}
      </div>
    </section>
  );
}
