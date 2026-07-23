import { useEffect, useState } from "react";

import {
  activateWorkflow,
  decideWorkflow,
  listWorkflowApprovals,
} from "./api";
import type { WorkflowVersion } from "./types";
import "./workflow-designer.css";

export function AdminWorkflowApprovalsPage() {
  const [items, setItems] = useState<WorkflowVersion[]>([]);
  const [factories, setFactories] = useState("");

  useEffect(() => {
    void listWorkflowApprovals().then((result) => setItems(result.items));
  }, []);

  async function approve(item: WorkflowVersion) {
    const updated = await decideWorkflow(item.version_id, "APPROVE");
    setItems((current) => current.map((value) => (
      value.version_id === updated.version_id ? updated : value
    )));
  }

  async function activate(item: WorkflowVersion) {
    await activateWorkflow(
      item.version_id,
      factories.split(",").map((value) => value.trim()).filter(Boolean),
    );
    setItems((current) => current.filter((value) => value.version_id !== item.version_id));
  }

  return (
    <section className="workflow-page">
      <header><h1>流程审核与启用</h1><p>只有预检通过的结构化版本可批准并按工厂启用。</p></header>
      <div className="workflow-card-list">
        {items.map((item) => (
          <article className="workflow-node-card" key={item.version_id}>
            <strong>{item.name}</strong>
            <span>版本 {item.version} · {item.status}</span>
            {item.status === "PENDING_APPROVAL" ? (
              <button type="button" onClick={() => void approve(item)}>批准流程</button>
            ) : (
              <>
                <label>
                  启用工厂
                  <input
                    aria-label="流程启用工厂"
                    value={factories}
                    onChange={(event) => setFactories(event.target.value)}
                  />
                </label>
                <button type="button" onClick={() => void activate(item)}>启用流程</button>
              </>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
