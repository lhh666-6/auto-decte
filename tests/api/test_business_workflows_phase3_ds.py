"""Phase 3 business discovery and governed workflow lifecycle."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services, build_services
from config.settings import Settings


def _add_user(services: Services, code: str, role: str) -> None:
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES,
        code,
        code,
        {},
        "phase-3-test",
        "workflow fixture",
    )
    services.mobile_identity_repository.set_credential(code, "2468")
    services.mobile_identity_repository.set_access_profile(
        code,
        team_id="",
        team_name="",
        position=role,
        roles=[role],
        allowed_form_types=[],
        allowed_processes=[],
        factory_id="",
        factory_name="",
        bamboo_role="",
    )


@pytest.fixture()
def services(tmp_path: Path) -> Services:
    built = build_services(Settings(data_root=tmp_path))
    _add_user(built, "FINANCE-1", "FINANCE")
    _add_user(built, "ADMIN-1", "ADMIN")
    return built


def _login(services: Services, code: str) -> TestClient:
    client = TestClient(create_app(services))
    assert client.post(
        "/api/v1/web/auth/login",
        json={"employee_code": code, "pin": "2468"},
    ).status_code == 200
    return client


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["web_csrf"]}


def test_discovery_requires_finance_confirmation_before_rule_is_executable(
    services: Services,
) -> None:
    finance = _login(services, "FINANCE-1")
    created = finance.post(
        "/api/v1/finance/business-discovery/sessions",
        headers=_csrf(finance),
        json={"source_refs": ["procedure:sorting"], "title": "分选流程梳理"},
    )
    assert created.status_code == 201
    session_id = created.json()["session_id"]

    message = finance.post(
        f"/api/v1/finance/business-discovery/sessions/{session_id}/messages",
        headers=_csrf(finance),
        json={"content": "主管审核通过后才能进入下游，并释放笼号。"},
    )
    assert message.status_code == 200
    rule = message.json()["proposed_rules"][0]
    assert rule["status"] == "PROPOSED"
    assert rule["executable"] is False

    confirmed = finance.post(
        f"/api/v1/finance/business-discovery/sessions/{session_id}/confirm",
        headers=_csrf(finance),
        json={
            "rule_ids": [rule["rule_id"]],
            "note": "已与现场确认",
        },
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["baseline"]["status"] == "CONFIRMED"
    assert confirmed.json()["rules"][0]["status"] == "CONFIRMED"
    assert confirmed.json()["rules"][0]["confirmed_by"] == "FINANCE-1"


def test_workflow_cannot_submit_until_preflight_passes(services: Services) -> None:
    finance = _login(services, "FINANCE-1")
    created = finance.post(
        "/api/v1/finance/workflows",
        headers=_csrf(finance),
        json={
            "workflow_key": "SORT_TO_DIP",
            "name": "分选到浸胶",
            "graph_json": {
                "nodes": [{"id": "start", "type": "FORM", "form_version_id": "missing"}],
                "edges": [],
                "start_node_id": "start",
            },
        },
    )
    assert created.status_code == 201
    version_id = created.json()["version_id"]

    invalid = finance.post(
        f"/api/v1/finance/workflow-versions/{version_id}/validate",
        headers=_csrf(finance),
    )
    assert invalid.status_code == 200
    assert invalid.json()["valid"] is False
    assert {item["code"] for item in invalid.json()["errors"]} >= {
        "END_NODE_REQUIRED",
        "FORM_VERSION_INACTIVE",
    }
    blocked = finance.post(
        f"/api/v1/finance/workflow-versions/{version_id}/submit-approval",
        headers=_csrf(finance),
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "WORKFLOW_PREFLIGHT_REQUIRED"


def test_admin_can_only_activate_approved_preflighted_workflow(
    services: Services,
) -> None:
    finance = _login(services, "FINANCE-1")
    created = finance.post(
        "/api/v1/finance/workflows",
        headers=_csrf(finance),
        json={
            "workflow_key": "NOTICE_ONLY",
            "name": "通知流程",
            "graph_json": {
                "nodes": [
                    {"id": "start", "type": "NOTIFICATION", "role": "PLANT_MANAGER"},
                    {"id": "end", "type": "END"},
                ],
                "edges": [{"source": "start", "target": "end"}],
                "start_node_id": "start",
            },
        },
    )
    version_id = created.json()["version_id"]
    assert finance.post(
        f"/api/v1/finance/workflow-versions/{version_id}/validate",
        headers=_csrf(finance),
    ).json()["valid"] is True
    assert finance.post(
        f"/api/v1/finance/workflow-versions/{version_id}/submit-approval",
        headers=_csrf(finance),
    ).status_code == 200

    admin = _login(services, "ADMIN-1")
    assert admin.post(
        f"/api/v1/admin/workflow-approvals/{version_id}/decision",
        headers=_csrf(admin),
        json={"decision": "APPROVE"},
    ).status_code == 200
    activated = admin.post(
        f"/api/v1/admin/workflow-versions/{version_id}/activate",
        headers=_csrf(admin),
        json={"plant_ids": ["FACTORY-A"]},
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "ACTIVE"
