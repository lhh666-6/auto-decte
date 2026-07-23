import { useState } from "react";

import { createWorkflow, validateWorkflow } from "./api";
import type { WorkflowNode } from "./types";
import "./workflow-designer.css";

const NODE_LABELS: Record<string, string> = {
  FORM: "表单",
  CONDITION: "条件",
  ROLE_CONFIRMATION: "角色确认",
  FIELD_MAPPING: "字段映射",
  NOTIFICATION: "通知",
  END: "结束",
};

export function WorkflowDesignerPage() {
  const [nodes, setNodes] = useState<WorkflowNode[]>([]);
  const [versionId, setVersionId] = useState("");
  const [errors, setErrors] = useState<Array<{ code: string; detail: string }>>([]);
  const [valid, setValid] = useState(false);

  function addNode(type: string) {
    setNodes((current) => [
      ...current,
      {
        id: `node-${current.length + 1}`,
        type,
        ...(type === "NOTIFICATION" ? { role: "PLANT_MANAGER" } : {}),
      },
    ]);
    setValid(false);
  }

  async function saveAndValidate() {
    const edges = nodes.slice(1).map((node, index) => ({
      source: nodes[index].id,
      target: node.id,
    }));
    const graph = { nodes, edges, start_node_id: nodes[0]?.id ?? "" };
    const workflow = await createWorkflow({
      workflow_key: `WORKFLOW_${Date.now()}`,
      name: "新业务流程",
      graph_json: graph,
      canvas_json: { zoom: 1 },
    });
    setVersionId(workflow.version_id);
    const report = await validateWorkflow(workflow.version_id);
    setErrors(report.errors);
    setValid(report.valid);
  }

  return (
    <section className="workflow-page">
      <header>
        <h1>可视化业务流程</h1>
        <p>添加结构化节点，保存后执行起点、终点、循环、权限和版本预检。</p>
      </header>
      <div className="workflow-node-palette" aria-label="流程节点工具箱">
        {Object.entries(NODE_LABELS).map(([type, label]) => (
          <button key={type} type="button" onClick={() => addNode(type)}>
            添加{label}节点
          </button>
        ))}
      </div>
      <div className="workflow-canvas">
        {nodes.map((node, index) => (
          <article key={node.id} className="workflow-node-card">
            <span>{index + 1}</span>
            <strong>{NODE_LABELS[node.type]}</strong>
            <small>{node.id}</small>
          </article>
        ))}
        {!nodes.length && <p>从上方选择节点开始设计。</p>}
      </div>
      <button type="button" disabled={!nodes.length} onClick={() => void saveAndValidate()}>
        保存并预检
      </button>
      {valid && <p role="status">流程预检通过：{versionId}</p>}
      {errors.length > 0 && (
        <div role="alert">
          <strong>流程预检未通过</strong>
          <ul>{errors.map((error) => <li key={error.code}>{error.detail}</li>)}</ul>
        </div>
      )}
    </section>
  );
}
