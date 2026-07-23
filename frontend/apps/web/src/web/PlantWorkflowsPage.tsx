import { useEffect, useState } from "react";

import { listPlantWorkflows } from "./api";
import type { WorkflowVersion } from "./types";
import "./workflow-designer.css";

export function PlantWorkflowsPage() {
  const [items, setItems] = useState<WorkflowVersion[]>([]);
  useEffect(() => {
    void listPlantWorkflows().then((result) => setItems(result.items));
  }, []);
  return (
    <section className="workflow-page">
      <header><h1>本厂流程</h1><p>当前本厂启用的流程版本，只读展示。</p></header>
      <div className="workflow-card-list">
        {items.map((item) => (
          <article className="workflow-node-card" key={item.version_id}>
            <strong>{item.name}</strong>
            <span>版本 {item.version} · 只读</span>
            <small>{item.graph_json.nodes.length} 个节点</small>
          </article>
        ))}
      </div>
    </section>
  );
}
