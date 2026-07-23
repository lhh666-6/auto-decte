import { useEffect, useState } from "react";

import { getPlantProduction, returnPlantRecord } from "./api";
import type { BambooProductionRecord } from "./types";
import "./ledger-pages.css";

const STAGES: Record<BambooProductionRecord["form_type"], Array<[string, string]>> = {
  SORTING: [["SORT", "分选"]],
  DIPPING_DRYING: [["DIPPING", "浸胶"], ["DRYING", "干燥"]],
};

export function PlantProductionPage() {
  const [records, setRecords] = useState<BambooProductionRecord[]>([]);
  const [overview, setOverview] = useState({ total: 0, active: 0, completed: 0 });
  const [selected, setSelected] = useState<BambooProductionRecord | null>(null);
  const [targetStages, setTargetStages] = useState<string[]>([]);
  const [reason, setReason] = useState("");
  const [error, setError] = useState("");

  function reload() {
    void getPlantProduction().then((result) => {
      setRecords(result.records);
      setOverview(result.overview);
    }).catch((cause: unknown) => setError(
      cause instanceof Error ? cause.message : "生产数据加载失败",
    ));
  }
  useEffect(reload, []);

  async function submitReturn() {
    if (!selected || !reason.trim() || !targetStages.length) return;
    try {
      await returnPlantRecord(selected.record_id, targetStages, reason, selected.revision);
      setSelected(null);
      setTargetStages([]);
      setReason("");
      reload();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "打回失败");
    }
  }

  return (
    <section className="ledger-page">
      <header>
        <h1>本厂竹丝生产看板</h1>
        <p>与工人移动端共用生产记录；厂长可选择需要重做的环节。</p>
      </header>
      {error && <div role="alert">{error}</div>}
      <div className="ledger-summary">
        <article><span>全部</span><strong>{overview.total}</strong></article>
        <article><span>进行中</span><strong>{overview.active}</strong></article>
        <article><span>已完成</span><strong>{overview.completed}</strong></article>
      </div>
      <div className="ledger-case-list">
        {records.map((record) => (
          <article key={record.record_id}>
            <strong>{record.display_no} · 笼号 {record.cage_no || "—"}</strong>
            <span>{record.current_stage || "已完成"} · {record.status}</span>
            <button type="button" onClick={() => {
              setSelected(record);
              setTargetStages([]);
            }}>选择环节打回</button>
          </article>
        ))}
        {!records.length && <p>当前没有生产记录。</p>}
      </div>
      {selected && (
        <div className="ledger-return-panel">
          <h2>打回 {selected.display_no}</h2>
          {STAGES[selected.form_type].map(([value, label]) => (
            <label key={value}>
              <input
                type="checkbox"
                aria-label={label}
                checked={targetStages.includes(value)}
                onChange={(event) => setTargetStages((current) => (
                  event.target.checked
                    ? [...current, value]
                    : current.filter((item) => item !== value)
                ))}
              />
              {label}
            </label>
          ))}
          <label>
            打回原因
            <textarea
              aria-label="打回原因"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>
          <button
            type="button"
            disabled={!reason.trim() || !targetStages.length}
            onClick={() => void submitReturn()}
          >确认打回</button>
          <button type="button" onClick={() => setSelected(null)}>取消</button>
        </div>
      )}
    </section>
  );
}
