import { useEffect, useState } from "react";

import { listPlantWorkflows } from "./api";
import type { BambooWorkflowStage } from "./types";
import "./workflow-designer.css";

export function PlantWorkflowsPage() {
  const [items, setItems] = useState<BambooWorkflowStage[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  function load() {
    setLoading(true);
    setError("");
    listPlantWorkflows()
      .then((result) => { setItems(result.items); setLoading(false); })
      .catch((cause: unknown) => {
        setError(cause instanceof Error ? cause.message : "流程加载失败");
        setLoading(false);
      });
  }
  useEffect(load, []);

  return (
    <section className="workflow-page">
      <header>
        <h1>竹丝生产流程 <span className="managed-status">只读</span></h1>
        <p>展示实际生产环节；本页没有流程启用审批权。</p>
      </header>
      {loading && <div role="status">正在加载流程…</div>}
      {error && (
        <div role="alert" className="error-banner">
          {error}{" "}
          <button type="button" onClick={load}>重试</button>
        </div>
      )}
      {!loading && !error && items.length === 0 && (
        <p>本厂暂未配置流程。</p>
      )}
      {!loading && !error && items.length > 0 && (
        <div className="workflow-card-list">
          {items.map((item) => (
            <article className="workflow-node-card" key={item.stage}>
              <strong>{item.label}</strong>
              <span>{item.stage}</span>
              <small>{item.returnable ? "可选择打回" : "只读或签字环节"}</small>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
