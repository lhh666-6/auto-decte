"""Workflow graphs must be safe before administrator activation."""

from app.modules.workflow_engine.preflight_ds import preflight_workflow


def _graph() -> dict[str, object]:
    return {
        "nodes": [
            {"id": "start", "type": "FORM", "form_version_id": "form-v1"},
            {"id": "approval", "type": "ROLE_CONFIRMATION", "role": "PLANT_MANAGER"},
            {"id": "end", "type": "END"},
        ],
        "edges": [
            {"source": "start", "target": "approval"},
            {"source": "approval", "target": "end"},
        ],
        "start_node_id": "start",
    }


def test_valid_structured_graph_passes_preflight() -> None:
    report = preflight_workflow(
        _graph(),
        active_form_version_ids={"form-v1"},
        confirmed_rule_ids={"rule-1"},
    )

    assert report.valid is True
    assert report.errors == []


def test_preflight_rejects_cycle_unreachable_node_and_missing_end() -> None:
    graph = _graph()
    graph["nodes"] = [
        {"id": "start", "type": "FORM", "form_version_id": "form-v1"},
        {"id": "loop", "type": "CONDITION"},
        {"id": "orphan", "type": "NOTIFICATION", "role": "FINANCE"},
    ]
    graph["edges"] = [
        {"source": "start", "target": "loop"},
        {"source": "loop", "target": "start"},
    ]

    report = preflight_workflow(
        graph,
        active_form_version_ids={"form-v1"},
        confirmed_rule_ids=set(),
    )

    assert report.valid is False
    assert {error.code for error in report.errors} >= {
        "END_NODE_REQUIRED",
        "UNREACHABLE_NODE",
        "WORKFLOW_CYCLE",
    }


def test_preflight_rejects_inactive_form_and_unconfirmed_rule() -> None:
    graph = _graph()
    graph["nodes"] = [
        *graph["nodes"],  # type: ignore[list-item]
        {"id": "rule", "type": "CONDITION", "rule_id": "rule-draft"},
    ]
    graph["edges"] = [
        {"source": "start", "target": "rule"},
        {"source": "rule", "target": "approval"},
        {"source": "approval", "target": "end"},
    ]

    report = preflight_workflow(
        graph,
        active_form_version_ids=set(),
        confirmed_rule_ids=set(),
    )

    assert {error.code for error in report.errors} >= {
        "FORM_VERSION_INACTIVE",
        "RULE_NOT_CONFIRMED",
    }


def test_preflight_rejects_unknown_nodes_and_dangling_edges() -> None:
    graph = _graph()
    graph["nodes"] = [
        {"id": "start", "type": "SCRIPT"},
        {"id": "end", "type": "END"},
    ]
    graph["edges"] = [{"source": "start", "target": "missing"}]

    report = preflight_workflow(
        graph,
        active_form_version_ids=set(),
        confirmed_rule_ids=set(),
    )

    assert {error.code for error in report.errors} >= {
        "UNSUPPORTED_NODE_TYPE",
        "DANGLING_EDGE",
        "END_NODE_UNREACHABLE",
    }
