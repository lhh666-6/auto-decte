import { useCallback, useEffect, useMemo, useState } from "react";

import {
  activateWorkflow,
  decideWorkflow,
  listWorkflowApprovals,
} from "./api";
import { VersionDiffPanel } from "./shared/VersionDiffPanel";
import type { DiffNode } from "./shared/VersionDiffPanel";
import { ReasonConfirmDialog } from "./shared/ReasonConfirmDialog";
import type { ImpactScope, PreCheckResult } from "./shared/ReasonConfirmDialog";
import type { WorkflowVersion } from "./types";
import "./workflow-designer.css";
import "./workspace.css";

/* ------------------------------------------------------------------ */
/*  helpers                                                            */
/* ------------------------------------------------------------------ */

function buildNodeDiff(
  current: WorkflowVersion,
  _previous?: WorkflowVersion,
): DiffNode[] {
  const nodes = current.graph_json.nodes ?? [];
  if (!_previous) {
    return nodes.map((n) => ({
      id: n.id,
      label: n.type,
      type: n.type,
      change: "added" as const,
      details: n.role ? `角色: ${n.role}` : undefined,
    }));
  }
  const prevNodeIds = new Set((_previous.graph_json.nodes ?? []).map((n) => n.id));
  return nodes.map((n) => {
    const existed = prevNodeIds.has(n.id);
    const prevNode = (_previous.graph_json.nodes ?? []).find((pn) => pn.id === n.id);
    let change: DiffNode["change"] = existed ? "unchanged" : "added";
    let details = n.role ? `角色: ${n.role}` : undefined;
    if (existed && prevNode && (prevNode.type !== n.type || prevNode.role !== n.role)) {
      change = "modified";
      details = prevNode.role !== n.role
        ? `角色变更: ${prevNode.role ?? "无"} -> ${n.role ?? "无"}`
        : `类型变更: ${prevNode.type} -> ${n.type}`;
    }
    return { id: n.id, label: n.type, type: n.type, change, details };
  });
}

function buildPreCheck(item: WorkflowVersion): PreCheckResult {
  const errors: string[] = [];
  const warnings: string[] = [];
  const { nodes, edges, start_node_id } = item.graph_json;

  /* orphan nodes */
  const referencedIds = new Set<string>();
  for (const edge of edges) {
    referencedIds.add(edge.source);
    referencedIds.add(edge.target);
  }
  const orphans = nodes.filter((n) => !referencedIds.has(n.id) && n.id !== start_node_id);
  if (orphans.length > 0) {
    errors.push(`孤立节点: ${orphans.map((n) => n.id).join(", ")}`);
  }

  /* circular dependency check (simple DFS) */
  const adj = new Map<string, string[]>();
  for (const edge of edges) {
    const targets = adj.get(edge.source) ?? [];
    targets.push(edge.target);
    adj.set(edge.source, targets);
  }
  function hasCycle(node: string, visited: Set<string>, stack: Set<string>): boolean {
    if (stack.has(node)) return true;
    if (visited.has(node)) return false;
    visited.add(node);
    stack.add(node);
    for (const neighbor of adj.get(node) ?? []) {
      if (hasCycle(neighbor, visited, stack)) return true;
    }
    stack.delete(node);
    return false;
  }
  const visited = new Set<string>();
  for (const node of nodes) {
    if (hasCycle(node.id, visited, new Set<string>())) {
      errors.push("检测到循环依赖");
      break;
    }
  }

  /* start node reachability */
  if (start_node_id && nodes.length > 0) {
    const reachable = new Set<string>();
    function dfs(id: string) {
      if (reachable.has(id)) return;
      reachable.add(id);
      for (const neighbor of adj.get(id) ?? []) dfs(neighbor);
    }
    dfs(start_node_id);
    const unreachable = nodes.filter((n) => !reachable.has(n.id));
    if (unreachable.length > 0) {
      warnings.push(`从起始节点不可达: ${unreachable.map((n) => n.id).join(", ")}`);
    }
  }

  return { passed: errors.length === 0, errors, warnings };
}

/* ------------------------------------------------------------------ */
/*  component                                                          */
/* ------------------------------------------------------------------ */

export function AdminWorkflowApprovalsPage() {
  const [items, setItems] = useState<WorkflowVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [factories, setFactories] = useState("");

  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogAction, setDialogAction] = useState<"APPROVE" | "REJECT">("APPROVE");
  const [dialogItem, setDialogItem] = useState<WorkflowVersion | null>(null);

  const fetchItems = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const result = await listWorkflowApprovals();
      setItems(result.items);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchItems();
  }, [fetchItems]);

  function openDialog(item: WorkflowVersion, action: "APPROVE" | "REJECT") {
    setDialogItem(item);
    setDialogAction(action);
    setDialogOpen(true);
  }

  function closeDialog() {
    setDialogOpen(false);
    setDialogItem(null);
  }

  async function handleConfirm(_reason: string) {
    if (!dialogItem) return;
    try {
      if (dialogAction === "APPROVE") {
        const updated = await decideWorkflow(dialogItem.version_id, "APPROVE");
        setItems((current) => current.map((v) => (v.version_id === updated.version_id ? updated : v)));
      } else {
        const updated = await decideWorkflow(dialogItem.version_id, "REJECT");
        setItems((current) => current.map((v) => (v.version_id === updated.version_id ? updated : v)));
      }
      closeDialog();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "审核失败");
      closeDialog();
    }
  }

  async function doActivate(item: WorkflowVersion) {
    await activateWorkflow(
      item.version_id,
      factories.split(",").map((v) => v.trim()).filter(Boolean),
    );
    setItems((current) => current.filter((v) => v.version_id !== item.version_id));
  }

  const dialogPreCheck = useMemo(
    () => (dialogItem ? buildPreCheck(dialogItem) : undefined),
    [dialogItem],
  );

  const dialogImpact = useMemo((): ImpactScope | undefined => {
    if (!dialogItem) return undefined;
    return {
      factories: factories.split(",").map((v) => v.trim()).filter(Boolean),
      affectedCount: dialogItem.graph_json.nodes.length,
    };
  }, [dialogItem, factories]);

  if (loading) return <div role="status" className="page-loading">正在加载流程审批列表...</div>;
  if (error && items.length === 0) return <div role="alert" className="error-banner">{error}</div>;

  return (
    <section className="workflow-page">
      <header>
        <h1>流程审核与启用</h1>
        <p>只有预检通过的结构化版本可批准并按工厂启用。</p>
      </header>

      {error && <div role="alert" className="error-banner">{error}</div>}

      {items.length === 0 ? (
        <p className="vex-empty">当前没有待审核流程。</p>
      ) : (
        <div className="workflow-card-list">
          {items.map((item) => {
            const preCheck = buildPreCheck(item);
            return (
              <article className="workflow-node-card" key={item.version_id}>
                <strong>{item.name}</strong>
                <span>版本 {item.version} · {item.status}</span>
                <span>{item.graph_json.nodes.length} 个节点 · {item.graph_json.edges.length} 条边</span>

                {/* node version diff */}
                <VersionDiffPanel
                  title="流程节点变化"
                  nodes={buildNodeDiff(item)}
                  emptyMessage="无上一版本可对比。"
                />

                {/* pre-check */}
                <div className={`precheck-summary ${preCheck.passed ? "precheck-passed" : "precheck-failed"}`}>
                  <strong>预检结果：{preCheck.passed ? "通过" : "未通过"}</strong>
                  {preCheck.errors.length > 0 && (
                    <ul>{preCheck.errors.map((e, i) => <li key={`e-${i}`}>{e}</li>)}</ul>
                  )}
                  {preCheck.warnings.length > 0 && (
                    <ul>{preCheck.warnings.map((w, i) => <li key={`w-${i}`}>{w}</li>)}</ul>
                  )}
                </div>

                {item.status === "PENDING_APPROVAL" ? (
                  <div className="managed-form-actions">
                    <button type="button" onClick={() => openDialog(item, "APPROVE")}>批准流程</button>
                    <button type="button" onClick={() => openDialog(item, "REJECT")}>退回修改</button>
                  </div>
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
                    <button type="button" onClick={() => void doActivate(item)}>启用流程</button>
                  </>
                )}
              </article>
            );
          })}
        </div>
      )}

      <ReasonConfirmDialog
        open={dialogOpen}
        title={dialogAction === "APPROVE" ? "批准流程版本" : "退回流程版本"}
        action={dialogAction}
        preCheck={dialogPreCheck}
        impactScope={dialogImpact}
        onConfirm={handleConfirm}
        onCancel={closeDialog}
      />
    </section>
  );
}
