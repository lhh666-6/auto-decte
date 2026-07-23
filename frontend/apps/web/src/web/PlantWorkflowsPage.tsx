import { useEffect, useState } from "react";

import { listPlantWorkflows } from "./api";
import type { BambooWorkflowStage } from "./types";
import "./workflow-designer.css";

export function PlantWorkflowsPage() {
  const [items, setItems] = useState<BambooWorkflowStage[]>([]);
  useEffect(() => {
    void listPlantWorkflows().then((result) => setItems(result.items));
  }, []);
  return (
    <section className="workflow-page">
      <header><h1>竹丝生产流程</h1><p>展示实际生产环节；本页没有流程启用审批权。</p></header>
      <div className="workflow-card-list">
        {items.map((item) => (
          <article className="workflow-node-card" key={item.stage}>
            <strong>{item.label}</strong>
            <span>{item.stage}</span>
            <small>{item.returnable ? "可选择打回" : "只读或签字环节"}</small>
          </article>
        ))}
      </div>
    </section>
  );
}
