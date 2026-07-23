"""Deterministic workflow validation used before approval and activation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

ALLOWED_NODE_TYPES = {
    "FORM",
    "CONDITION",
    "ROLE_CONFIRMATION",
    "FIELD_MAPPING",
    "NOTIFICATION",
    "END",
}


@dataclass(frozen=True, slots=True)
class PreflightError:
    code: str
    detail: str
    node_id: str = ""


@dataclass(frozen=True, slots=True)
class PreflightReport:
    valid: bool
    errors: list[PreflightError]


def preflight_workflow(
    graph: dict[str, Any],
    *,
    active_form_version_ids: set[str],
    confirmed_rule_ids: set[str],
    allowed_factory_ids: set[str] | None = None,
    field_types: dict[str, str] | None = None,
) -> PreflightReport:
    errors: list[PreflightError] = []
    raw_nodes = graph.get("nodes")
    raw_edges = graph.get("edges")
    nodes = raw_nodes if isinstance(raw_nodes, list) else []
    edges = raw_edges if isinstance(raw_edges, list) else []

    node_by_id: dict[str, dict[str, Any]] = {}
    for raw_node in nodes:
        if not isinstance(raw_node, dict):
            errors.append(PreflightError("INVALID_NODE", "节点必须是结构化对象。"))
            continue
        node = raw_node
        node_id = str(node.get("id", "")).strip()
        if not node_id:
            errors.append(PreflightError("NODE_ID_REQUIRED", "节点缺少标识。"))
            continue
        if node_id in node_by_id:
            errors.append(PreflightError("DUPLICATE_NODE_ID", "节点标识重复。", node_id))
            continue
        node_by_id[node_id] = node
        _validate_node(
            node,
            node_id,
            errors,
            active_form_version_ids=active_form_version_ids,
            confirmed_rule_ids=confirmed_rule_ids,
            allowed_factory_ids=allowed_factory_ids,
            field_types=field_types,
        )

    start_id = str(graph.get("start_node_id", "")).strip()
    if not start_id or start_id not in node_by_id:
        errors.append(PreflightError("START_NODE_REQUIRED", "流程必须指定有效起点。"))

    end_ids = {
        node_id
        for node_id, node in node_by_id.items()
        if node.get("type") == "END"
    }
    if not end_ids:
        errors.append(PreflightError("END_NODE_REQUIRED", "流程至少需要一个结束节点。"))

    adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_by_id}
    outgoing_edges: dict[str, list[dict[str, Any]]] = {
        node_id: [] for node_id in node_by_id
    }
    for raw_edge in edges:
        if not isinstance(raw_edge, dict):
            errors.append(PreflightError("INVALID_EDGE", "连线必须是结构化对象。"))
            continue
        source = str(raw_edge.get("source", "")).strip()
        target = str(raw_edge.get("target", "")).strip()
        if source not in node_by_id or target not in node_by_id:
            errors.append(
                PreflightError(
                    "DANGLING_EDGE",
                    "连线引用了不存在的节点。",
                    source or target,
                )
            )
            continue
        adjacency[source].append(target)
        outgoing_edges[source].append(raw_edge)

    if start_id in node_by_id:
        reachable = _reachable(start_id, adjacency)
        for node_id in node_by_id.keys() - reachable:
            errors.append(
                PreflightError("UNREACHABLE_NODE", "节点无法从起点到达。", node_id)
            )
        if end_ids and not (end_ids & reachable):
            errors.append(
                PreflightError("END_NODE_UNREACHABLE", "流程无法到达结束节点。")
            )

    if _has_cycle(adjacency):
        errors.append(PreflightError("WORKFLOW_CYCLE", "流程存在循环路径。"))

    for node_id, node in node_by_id.items():
        if node.get("type") == "CONDITION":
            branches = outgoing_edges[node_id]
            labels = {str(edge.get("branch", "")).upper() for edge in branches}
            if len(branches) < 2 or not {"TRUE", "FALSE"}.issubset(labels):
                errors.append(
                    PreflightError(
                        "CONDITION_BRANCH_INCOMPLETE",
                        "条件节点必须覆盖是和否两个分支。",
                        node_id,
                    )
                )

    return PreflightReport(valid=not errors, errors=errors)


def _validate_node(
    node: dict[str, Any],
    node_id: str,
    errors: list[PreflightError],
    *,
    active_form_version_ids: set[str],
    confirmed_rule_ids: set[str],
    allowed_factory_ids: set[str] | None,
    field_types: dict[str, str] | None,
) -> None:
    node_type = str(node.get("type", "")).upper()
    if node_type not in ALLOWED_NODE_TYPES:
        errors.append(
            PreflightError("UNSUPPORTED_NODE_TYPE", "流程包含不支持的节点类型。", node_id)
        )
        return
    if node_type == "FORM":
        version_id = str(node.get("form_version_id", ""))
        if version_id not in active_form_version_ids:
            errors.append(
                PreflightError(
                    "FORM_VERSION_INACTIVE",
                    "表单节点引用的版本未启用。",
                    node_id,
                )
            )
    if node_type == "CONDITION" and node.get("rule_id"):
        if str(node["rule_id"]) not in confirmed_rule_ids:
            errors.append(
                PreflightError(
                    "RULE_NOT_CONFIRMED",
                    "条件节点引用的业务规则尚未由财务确认。",
                    node_id,
                )
            )
    if node_type in {"ROLE_CONFIRMATION", "NOTIFICATION"} and not node.get("role"):
        errors.append(
            PreflightError("ROLE_REQUIRED", "该节点必须指定目标角色。", node_id)
        )
    if allowed_factory_ids is not None:
        plant_ids = {str(value) for value in node.get("plant_ids", [])}
        if plant_ids - allowed_factory_ids:
            errors.append(
                PreflightError(
                    "CROSS_FACTORY_FORBIDDEN",
                    "节点包含无权使用的工厂。",
                    node_id,
                )
            )
    if node_type == "FIELD_MAPPING" and field_types is not None:
        source = str(node.get("source_field", ""))
        target = str(node.get("target_field", ""))
        if source not in field_types or target not in field_types:
            errors.append(
                PreflightError("MAPPING_FIELD_MISSING", "字段映射引用不存在。", node_id)
            )
        elif field_types[source] != field_types[target]:
            errors.append(
                PreflightError("MAPPING_TYPE_MISMATCH", "字段映射类型不一致。", node_id)
            )


def _reachable(start_id: str, adjacency: dict[str, list[str]]) -> set[str]:
    visited: set[str] = set()
    pending = [start_id]
    while pending:
        node_id = pending.pop()
        if node_id in visited:
            continue
        visited.add(node_id)
        pending.extend(adjacency.get(node_id, []))
    return visited


def _has_cycle(adjacency: dict[str, list[str]]) -> bool:
    visited: set[str] = set()
    active: set[str] = set()

    def visit(node_id: str) -> bool:
        if node_id in active:
            return True
        if node_id in visited:
            return False
        visited.add(node_id)
        active.add(node_id)
        if any(visit(target) for target in adjacency.get(node_id, [])):
            return True
        active.remove(node_id)
        return False

    return any(visit(node_id) for node_id in adjacency)
