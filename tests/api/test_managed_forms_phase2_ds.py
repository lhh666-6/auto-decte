"""Phase 2 managed electronic-form lifecycle."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services, build_services
from config.settings import Settings


def _add_user(
    services: Services,
    employee_code: str,
    role: str,
    *,
    factory_id: str = "",
) -> None:
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES,
        employee_code,
        employee_code,
        {},
        "phase-2-test",
        "managed form fixture",
    )
    services.mobile_identity_repository.set_credential(employee_code, "2468")
    services.mobile_identity_repository.set_access_profile(
        employee_code,
        team_id="",
        team_name="",
        position=role,
        roles=[role],
        allowed_form_types=[],
        allowed_processes=[],
        factory_id=factory_id,
        factory_name=factory_id,
        bamboo_role="",
    )


@pytest.fixture()
def services(tmp_path: Path) -> Services:
    built = build_services(Settings(data_root=tmp_path))
    _add_user(built, "ADMIN-1", "ADMIN")
    _add_user(built, "FINANCE-1", "FINANCE")
    _add_user(built, "MANAGER-A", "PLANT_MANAGER", factory_id="FACTORY-A")
    _add_user(built, "MANAGER-B", "PLANT_MANAGER", factory_id="FACTORY-B")
    _add_user(built, "WORKER-A", "WORKER", factory_id="FACTORY-A")
    return built


def _login(services: Services, employee_code: str) -> TestClient:
    client = TestClient(create_app(services))
    result = client.post(
        "/api/v1/web/auth/login",
        json={"employee_code": employee_code, "pin": "2468"},
    )
    assert result.status_code == 200
    return client


def _csrf(client: TestClient) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["web_csrf"]}


def _create_draft(client: TestClient) -> dict[str, object]:
    result = client.post(
        "/api/v1/finance/form-definitions",
        headers=_csrf(client),
        json={
            "form_key": "DAILY_OUTPUT",
            "name": "日产量表",
            "owner_role": "WORKER",
            "schema_json": {
                "fields": [
                    {"key": "quantity", "label": "产量", "type": "number", "required": True}
                ]
            },
        },
    )
    assert result.status_code == 201, result.text
    return result.json()


def test_finance_draft_requires_csrf_and_is_revision_checked(services: Services) -> None:
    finance = _login(services, "FINANCE-1")
    denied = finance.post(
        "/api/v1/finance/form-definitions",
        json={"form_key": "X", "name": "X", "owner_role": "WORKER", "schema_json": {}},
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "CSRF_VALIDATION_FAILED"

    created = _create_draft(finance)
    version_id = str(created["version_id"])
    assert created["status"] == "DRAFT"
    assert created["version"] == 1

    updated = finance.patch(
        f"/api/v1/finance/form-versions/{version_id}",
        headers=_csrf(finance),
        json={
            "expected_revision": 1,
            "schema_json": {"fields": [{"key": "quantity", "type": "integer"}]},
        },
    )
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2

    conflict = finance.patch(
        f"/api/v1/finance/form-versions/{version_id}",
        headers=_csrf(finance),
        json={"expected_revision": 1, "schema_json": {"fields": []}},
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "FORM_VERSION_REVISION_CONFLICT"


def test_admin_approval_activation_and_immutable_version(services: Services) -> None:
    finance = _login(services, "FINANCE-1")
    created = _create_draft(finance)
    version_id = str(created["version_id"])

    submitted = finance.post(
        f"/api/v1/finance/form-versions/{version_id}/submit-approval",
        headers=_csrf(finance),
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "PENDING_APPROVAL"

    admin = _login(services, "ADMIN-1")
    approvals = admin.get("/api/v1/admin/form-approvals")
    assert [item["version_id"] for item in approvals.json()["items"]] == [version_id]

    approved = admin.post(
        f"/api/v1/admin/form-approvals/{version_id}/decision",
        headers=_csrf(admin),
        json={"decision": "APPROVE", "comment": "字段完整"},
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"

    activated = admin.post(
        f"/api/v1/admin/form-versions/{version_id}/activate",
        headers=_csrf(admin),
        json={"plant_ids": ["FACTORY-A"]},
    )
    assert activated.status_code == 200
    assert activated.json()["plant_ids"] == ["FACTORY-A"]

    immutable = finance.patch(
        f"/api/v1/finance/form-versions/{version_id}",
        headers=_csrf(finance),
        json={"expected_revision": 2, "schema_json": {"fields": []}},
    )
    assert immutable.status_code == 409
    assert immutable.json()["code"] == "FORM_VERSION_IMMUTABLE"

    cloned = finance.post(
        f"/api/v1/finance/form-versions/{version_id}/clone",
        headers=_csrf(finance),
    )
    assert cloned.status_code == 201
    assert cloned.json()["version"] == 2
    assert cloned.json()["status"] == "DRAFT"

    version_2_id = cloned.json()["version_id"]
    finance.post(
        f"/api/v1/finance/form-versions/{version_2_id}/submit-approval",
        headers=_csrf(finance),
    )
    admin.post(
        f"/api/v1/admin/form-approvals/{version_2_id}/decision",
        headers=_csrf(admin),
        json={"decision": "APPROVE"},
    )
    admin.post(
        f"/api/v1/admin/form-versions/{version_2_id}/activate",
        headers=_csrf(admin),
        json={"plant_ids": ["FACTORY-A"]},
    )
    current = _login(services, "MANAGER-A").get("/api/v1/plant/forms").json()["items"]
    assert [item["version_id"] for item in current] == [version_2_id]
    assert finance.get(f"/api/v1/finance/form-versions/{version_id}").status_code == 200


def test_plant_sees_only_own_active_forms_and_notice_does_not_block(
    services: Services,
) -> None:
    finance = _login(services, "FINANCE-1")
    version_id = str(_create_draft(finance)["version_id"])
    finance.post(
        f"/api/v1/finance/form-versions/{version_id}/submit-approval",
        headers=_csrf(finance),
    )
    admin = _login(services, "ADMIN-1")
    admin.post(
        f"/api/v1/admin/form-approvals/{version_id}/decision",
        headers=_csrf(admin),
        json={"decision": "APPROVE"},
    )
    admin.post(
        f"/api/v1/admin/form-versions/{version_id}/activate",
        headers=_csrf(admin),
        json={"plant_ids": ["FACTORY-A"]},
    )

    manager_a = _login(services, "MANAGER-A")
    forms_a = manager_a.get("/api/v1/plant/forms")
    assert [item["form_key"] for item in forms_a.json()["items"]] == ["DAILY_OUTPUT"]
    notices = manager_a.get("/api/v1/plant/notifications")
    assert notices.json()["items"][0]["acknowledged_at"] is None

    manager_b = _login(services, "MANAGER-B")
    assert manager_b.get("/api/v1/plant/forms").json()["items"] == []

    mobile = TestClient(create_app(services))
    login = mobile.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": "WORKER-A", "pin": "2468", "device_id": "android-a"},
    )
    assert login.status_code == 200
    available = mobile.get("/api/v1/mobile/available-forms")
    assert [item["form_type"] for item in available.json()["forms"]] == ["DAILY_OUTPUT"]
    schema = mobile.get("/api/v1/mobile/form-schemas/DAILY_OUTPUT")
    assert schema.status_code == 200
    assert schema.json()["definition_version_id"] == version_id
    assert schema.json()["fields"][0]["field_name"] == "quantity"

    notice_id = notices.json()["items"][0]["notification_id"]
    acknowledged = manager_a.post(
        f"/api/v1/plant/notifications/{notice_id}/acknowledge",
        headers=_csrf(manager_a),
    )
    assert acknowledged.status_code == 200
    assert acknowledged.json()["acknowledged_at"] is not None
    assert manager_a.get("/api/v1/plant/forms").json()["items"][0]["version_id"] == version_id


def test_disable_restore_and_retire_are_factory_scoped(services: Services) -> None:
    finance = _login(services, "FINANCE-1")
    version_id = str(_create_draft(finance)["version_id"])
    finance.post(
        f"/api/v1/finance/form-versions/{version_id}/submit-approval",
        headers=_csrf(finance),
    )
    admin = _login(services, "ADMIN-1")
    admin.post(
        f"/api/v1/admin/form-approvals/{version_id}/decision",
        headers=_csrf(admin),
        json={"decision": "APPROVE"},
    )
    admin.post(
        f"/api/v1/admin/form-versions/{version_id}/activate",
        headers=_csrf(admin),
        json={"plant_ids": ["FACTORY-A", "FACTORY-B"]},
    )

    disabled = admin.post(
        f"/api/v1/admin/form-versions/{version_id}/disable",
        headers=_csrf(admin),
        json={"plant_ids": ["FACTORY-A"]},
    )
    assert disabled.status_code == 200
    assert _login(services, "MANAGER-A").get("/api/v1/plant/forms").json()["items"] == []
    assert len(_login(services, "MANAGER-B").get("/api/v1/plant/forms").json()["items"]) == 1

    restored = admin.post(
        f"/api/v1/admin/form-versions/{version_id}/restore",
        headers=_csrf(admin),
        json={"plant_ids": ["FACTORY-A"]},
    )
    assert restored.status_code == 200
    assert len(_login(services, "MANAGER-A").get("/api/v1/plant/forms").json()["items"]) == 1

    retired = admin.post(
        f"/api/v1/admin/form-versions/{version_id}/retire",
        headers=_csrf(admin),
        json={"plant_ids": ["FACTORY-A", "FACTORY-B"]},
    )
    assert retired.status_code == 200
    assert _login(services, "MANAGER-A").get("/api/v1/plant/forms").json()["items"] == []
