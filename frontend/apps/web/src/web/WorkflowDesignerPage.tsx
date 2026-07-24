import { useState } from "react";

import { createWorkflow, validateWorkflow } from "./api";
import type { WorkflowNode } from "./types";
import { ReasonConfirmDialog, PageHeader, EmptyState, ErrorAlert } from "./shared";
import type { PreCheckResult } from "./shared";
import "./workflow-designer.css";
import "./finance-pages.css";

const NODE_LABELS: Record<string, string> = {
  FORM: "表单",
  CONDITION: "条件",
  ROLE_CONFIRMATION: "角色确认",
  FIELD_MAPPING: "字段映射",
  NOTIFICATION: "通知",
  END: "结束",
};

const NODE_TYPE_ORDER = ["FORM", "CONDITION", "ROLE_CONFIRMATION", "FIELD_MAPPING", "NOTIFICATION", "END"];

function classifyCheckErrors(
  errors: Array<{ code: string; detail: string; node_id: string }>,
): PreCheckResult {
  const preCheck: PreCheckResult = { passed: true, errors: [], warnings: [] };
  for (const e of errors) {
    if (
      e.code === "ORPHAN_NODE" ||
      e.code === "CYCLE_DETECTED" ||
      e.code === "MISSING_START" ||
      e.code === "MISSING_END"
    ) {
      preCheck.errors.push(`[${e.code}] ${e.detail} (节点: ${e.node_id || "—"})`);
    } else {
      preCheck.warnings.push(`[${e.code}] ${e.detail} (节点: ${e.node_id || "—"})`);
    }
  }
  if (errors.length > 0) preCheck.passed = false;
  return preCheck;
}

export function WorkflowDesignerPage() {
  const [nodes, setNodes] = useState<WorkflowNode[]>([]);
  const [versionId, setVersionId] = useState("");
  const [errors, setErrors] = useState<Array<{ code: string; detail: string; node_id: string }>>([]);
  const [valid, setValid] = useState(false);
  const [selectedNode, setSelectedNode] = useState<WorkflowNode | null>(null);
  const [preCheck, setPreCheck] = useState<PreCheckResult | null>(null);
  const [showSubmitDialog, setShowSubmitDialog] = useState(false);
  const [pageError, setPageError] = useState("");

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
    setPreCheck(null);
  }

  function removeNode(index: number) {
    setNodes((current) => current.filter((_, i) => i !== index));
    if (selectedNode && nodes[index]?.id === selectedNode.id) {
      setSelectedNode(null);
    }
    setValid(false);
    setPreCheck(null);
  }

  function updateNode(index: number, patch: Partial<WorkflowNode>) {
    setNodes((current) =>
      current.map((n, i) => (i === index ? { ...n, ...patch } : n)),
    );
    if (selectedNode && nodes[index]?.id === selectedNode.id) {
      setSelectedNode({ ...nodes[index], ...patch });
    }
    setValid(false);
    setPreCheck(null);
  }

  async function saveAndValidate() {
    if (nodes.length === 0) {
      setPageError("请先添加至少一个节点");
      return;
    }
    setPageError("");
    const edges = nodes.slice(1).map((node, index) => ({
      source: nodes[index].id,
      target: node.id,
    }));
    const graph = { nodes, edges, start_node_id: nodes[0]?.id ?? "" };
    try {
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
      setPreCheck(classifyCheckErrors(report.errors));
    } catch (cause) {
      setPageError(cause instanceof Error ? cause.message : "保存并预检失败");
    }
  }

  function openSubmitApproval() {
    if (!valid) {
      void saveAndValidate();
      return;
    }
    setShowSubmitDialog(true);
  }

  function confirmSubmitApproval(_reason: string) {
    setShowSubmitDialog(false);
    // In a production app, this would call the actual submit API.
    setPageError("");
  }

  return (
    <section className="workflow-page">
      <PageHeader title="可视化业务流程" subtitle="添加结构化节点，保存后执行起点、终点、循环、权限和版本预检。" />

      {pageError && <ErrorAlert message={pageError} />}

      {/* Node palette */}
      <div className="workflow-node-palette" aria-label="流程节点工具箱" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        {NODE_TYPE_ORDER.map((type) => (
          <button
            key={type}
            type="button"
            onClick={() => addNode(type)}
            style={{ padding: "6px 14px", border: "1px solid #b9c6d5", borderRadius: 6, background: "#fff", font: "inherit", fontSize: 13, cursor: "pointer" }}
          >
            + {NODE_LABELS[type]}
          </button>
        ))}
      </div>

      {nodes.length === 0 ? (
        <EmptyState message="从上方选择节点开始设计。" />
      ) : (
        <div className="workflow-two-column">
          {/* Canvas area */}
          <div className="workflow-canvas-area">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <span style={{ color: "#596579", fontSize: 13 }}>共 {nodes.length} 个节点</span>
              <div style={{ display: "flex", gap: 8 }}>
                <button
                  type="button"
                  onClick={() => void saveAndValidate()}
                  style={{ padding: "6px 14px", border: "1px solid #155eef", borderRadius: 6, color: "#155eef", background: "#fff", font: "inherit", fontSize: 13, fontWeight: 650, cursor: "pointer" }}
                >
                  保存并预检
                </button>
                {valid && (
                  <button
                    type="button"
                    onClick={openSubmitApproval}
                    style={{ padding: "6px 14px", border: 0, borderRadius: 6, color: "#fff", background: "#155eef", font: "inherit", fontSize: 13, fontWeight: 650, cursor: "pointer" }}
                  >
                    提交审批
                  </button>
                )}
              </div>
            </div>

            {nodes.map((node, index) => (
              <div
                key={node.id}
                className={`workflow-node-card${selectedNode?.id === node.id ? " workflow-node-card--selected" : ""}`}
                onClick={() => setSelectedNode(node)}
              >
                <span className={`workflow-node-index ${node.type}`}>{index + 1}</span>
                <div className="workflow-node-info">
                  <strong>{NODE_LABELS[node.type] ?? node.type}</strong>
                  <small>{node.id}</small>
                  {node.role && <small style={{ color: "#155eef" }}>执行岗位: {node.role}</small>}
                  {node.form_version_id && <small>表单版本: {node.form_version_id}</small>}
                </div>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); removeNode(index); }}
                  style={{ padding: "4px 10px", border: "1px solid #e7b4b4", borderRadius: 4, background: "#fff", color: "#9d2424", fontSize: 12, cursor: "pointer" }}
                >
                  移除
                </button>
              </div>
            ))}

            {valid && (
              <div role="status" style={{ color: "#1a6b3c", fontSize: 13, fontWeight: 650 }}>
                流程预检通过 — 版本: {versionId}
              </div>
            )}
          </div>

          {/* Properties panel */}
          <div className="workflow-props-panel">
            <h3>节点属性</h3>
            {selectedNode ? (
              <div className="workflow-props-kv">
                <div className="workflow-props-row">
                  <dt>节点ID</dt>
                  <dd style={{ fontFamily: "monospace", fontSize: 12 }}>{selectedNode.id}</dd>
                </div>
                <div className="workflow-props-row">
                  <dt>记录类型</dt>
                  <dd>{NODE_LABELS[selectedNode.type] ?? selectedNode.type}</dd>
                </div>
                {selectedNode.role !== undefined && (
                  <div className="workflow-props-row">
                    <dt>执行岗位</dt>
                    <dd>{selectedNode.role || "—"}</dd>
                  </div>
                )}
                <div className="workflow-props-row">
                  <dt>前置节点</dt>
                  <dd>
                    {(() => {
                      const idx = nodes.findIndex((n) => n.id === selectedNode.id);
                      return idx > 0
                        ? `${NODE_LABELS[nodes[idx - 1].type]} (${nodes[idx - 1].id})`
                        : idx === 0
                          ? "起点节点"
                          : "—";
                    })()}
                  </dd>
                </div>
                {selectedNode.form_version_id !== undefined && (
                  <div className="workflow-props-row">
                    <dt>表单版本</dt>
                    <dd>{selectedNode.form_version_id || "—"}</dd>
                  </div>
                )}
                <div className="workflow-props-row">
                  <dt>开放条件</dt>
                  <dd style={{ color: "#8593a8", fontSize: 12 }}>
                    {selectedNode.type === "CONDITION" ? "需配置条件表达式" : "无条件"}
                  </dd>
                </div>
                <div className="workflow-props-row">
                  <dt>完成条件</dt>
                  <dd style={{ color: "#8593a8", fontSize: 12 }}>节点完成即推进</dd>
                </div>
                <div className="workflow-props-row">
                  <dt>失败/退回</dt>
                  <dd style={{ color: "#8593a8", fontSize: 12 }}>
                    {selectedNode.type === "END" ? "不可退回" : "可退回至上一节点"}
                  </dd>
                </div>
                <div className="workflow-props-row">
                  <dt>版本</dt>
                  <dd>{versionId ? `V1 (${versionId.slice(0, 8)})` : "未保存"}</dd>
                </div>
              </div>
            ) : (
              <p className="workflow-props-empty">点击节点查看属性</p>
            )}

            {/* Inline node editor for selected */}
            {selectedNode && (
              <div style={{ display: "grid", gap: 8, paddingTop: 8, borderTop: "1px solid #e7ecf2" }}>
                <label style={{ display: "grid", gap: 4, fontSize: 12, color: "#42566f" }}>
                  表单版本ID
                  <input
                    value={selectedNode.form_version_id ?? ""}
                    onChange={(e) => {
                      const idx = nodes.findIndex((n) => n.id === selectedNode.id);
                      if (idx >= 0) updateNode(idx, { form_version_id: e.target.value });
                    }}
                    placeholder="输入关联的表单版本ID"
                    style={{ padding: "6px 8px", border: "1px solid #b9c6d5", borderRadius: 4, font: "inherit", fontSize: 12 }}
                  />
                </label>
                <label style={{ display: "grid", gap: 4, fontSize: 12, color: "#42566f" }}>
                  执行角色
                  <input
                    value={selectedNode.role ?? ""}
                    onChange={(e) => {
                      const idx = nodes.findIndex((n) => n.id === selectedNode.id);
                      if (idx >= 0) updateNode(idx, { role: e.target.value });
                    }}
                    placeholder="如 PLANT_MANAGER"
                    style={{ padding: "6px 8px", border: "1px solid #b9c6d5", borderRadius: 4, font: "inherit", fontSize: 12 }}
                  />
                </label>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Pre-check results */}
      {preCheck && (
        <div className={`workflow-precheck-banner workflow-precheck-banner--${preCheck.passed ? "pass" : "fail"}`}>
          <strong>预检结果：{preCheck.passed ? "通过" : "未通过"}</strong>
          {preCheck.errors.length > 0 && (
            <>
              <span>阻断级错误：</span>
              <ul>
                {preCheck.errors.map((err, i) => (
                  <li key={`e-${i}`}>{err}</li>
                ))}
              </ul>
            </>
          )}
          {preCheck.warnings.length > 0 && (
            <>
              <span>警告：</span>
              <ul>
                {preCheck.warnings.map((w, i) => (
                  <li key={`w-${i}`}>{w}</li>
                ))}
              </ul>
            </>
          )}
          <button
            type="button"
            style={{ justifySelf: "start", padding: "4px 10px", fontSize: 12, border: "1px solid currentColor", borderRadius: 4, background: "transparent", cursor: "pointer", color: "inherit" }}
            onClick={() => setPreCheck(null)}
          >
            关闭
          </button>
        </div>
      )}

      {/* Error details from API */}
      {errors.length > 0 && !preCheck && (
        <div role="alert" style={{ padding: "12px 16px", background: "#fef5f5", border: "1px solid #f0b8b8", borderRadius: 8, color: "#9d2424", fontSize: 13 }}>
          <strong>流程预检未通过</strong>
          <ul style={{ margin: "6px 0 0", paddingLeft: 18 }}>
            {errors.map((err) => (
              <li key={err.code + err.node_id}>{err.detail} (节点: {err.node_id || "—"})</li>
            ))}
          </ul>
        </div>
      )}

      {/* Submit approval dialog */}
      <ReasonConfirmDialog
        open={showSubmitDialog}
        title="提交流程审批"
        action="APPROVE"
        preCheck={preCheck ?? undefined}
        onConfirm={(reason) => { confirmSubmitApproval(reason); }}
        onCancel={() => setShowSubmitDialog(false)}
      />
    </section>
  );
}
