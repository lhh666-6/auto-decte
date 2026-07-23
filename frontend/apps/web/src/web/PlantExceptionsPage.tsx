import { useEffect, useState } from "react";

import { decidePlantInspectionAppeal, getPlantExceptions } from "./api";
import type { BambooInspectionQueueItem } from "./types";
import "./ledger-pages.css";

export function PlantExceptionsPage() {
  const [items, setItems] = useState<BambooInspectionQueueItem[]>([]);
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");

  function reload() {
    void getPlantExceptions("active", query).then((result) => setItems(result.items))
      .catch((cause: unknown) => setError(
        cause instanceof Error ? cause.message : "检测队列加载失败",
      ));
  }
  useEffect(reload, []);

  async function decide(recordId: string, approve: boolean) {
    try {
      await decidePlantInspectionAppeal(
        recordId,
        approve,
        approve ? "厂长批准回溯" : "厂长驳回上诉",
      );
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "审批失败");
    }
  }

  return (
    <section className="ledger-page">
      <header><h1>检测队列与上诉</h1><p>查看两小时检测窗口及 24 小时上诉结果。</p></header>
      {error && <div role="alert">{error}</div>}
      <label>
        搜索表号或笼号
        <input value={query} onChange={(event) => setQuery(event.target.value)} />
      </label>
      <button type="button" onClick={reload}>搜索</button>
      <div className="ledger-case-list">
        {items.map((item) => (
          <article key={item.record_id}>
            <strong>{item.display_no} · {item.cage_no || "无笼号"}</strong>
            <span>{item.status} · 截止 {item.deadline_at}</span>
            {item.appeal_payload && (
              <>
                <p>{item.appeal_payload.text_evidence}</p>
                <button type="button" onClick={() => void decide(item.record_id, true)}>
                  批准回溯
                </button>
                <button type="button" onClick={() => void decide(item.record_id, false)}>
                  驳回上诉
                </button>
              </>
            )}
          </article>
        ))}
        {!items.length && <p>当前没有检测待办。</p>}
      </div>
    </section>
  );
}
