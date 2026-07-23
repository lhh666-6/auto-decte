"""Phase 5 payroll governance APIs and salary visibility."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.modules.submission_ledger.service_ds import SubmissionLedgerService
from app.services.container import Services, build_services
from config.settings import Settings


def _add_user(services: Services, code: str, role: str, factory_id: str = "") -> None:
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES, code, code, {}, "phase-5", "fixture"
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
        factory_id=factory_id,
        factory_name=factory_id,
        bamboo_role="",
    )


@pytest.fixture()
def services(tmp_path: Path) -> Services:
    built = build_services(Settings(data_root=tmp_path))
    _add_user(built, "FINANCE-1", "FINANCE")
    _add_user(built, "ADMIN-1", "ADMIN")
    _add_user(built, "MANAGER-A", "PLANT_MANAGER", "FACTORY-A")
    _add_user(built, "MANAGER-B", "PLANT_MANAGER", "FACTORY-B")
    ledger = SubmissionLedgerService(built.engine)
    for submission_id, factory_id, employee in (
        ("SUB-A", "FACTORY-A", "E001"),
        ("SUB-B", "FACTORY-B", "E002"),
    ):
        ledger.record_acceptance(
            submission_id=submission_id,
            factory_id=factory_id,
            subject_employee_code=employee,
            actor_id=employee,
            definition_version_id="FORM-V1",
            values={"quantity": 10},
            submitted_at=datetime(2026, 7, 1, tzinfo=UTC),
        )
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


def test_rule_approval_calculation_confirmation_and_scoped_views(
    services: Services,
) -> None:
    finance = _login(services, "FINANCE-1")
    admin = _login(services, "ADMIN-1")
    manager_a = _login(services, "MANAGER-A")
    manager_b = _login(services, "MANAGER-B")

    draft = finance.post(
        "/api/v1/finance/payroll-rules",
        headers=_csrf(finance),
        json={
            "rule_key": "PIECE",
            "name": "计件工资",
            "factory_id": "FACTORY-A",
            "position": "WORKER",
            "dsl": {"metric": "quantity", "rate": "2", "base": "0"},
        },
    ).json()
    version_id = draft["rule_version_id"]
    assert finance.post(
        f"/api/v1/finance/payroll-rules/{version_id}/submit-approval",
        headers=_csrf(finance),
    ).status_code == 200
    assert admin.get("/api/v1/admin/payroll-approvals").json()["items"][0]["status"] == (
        "PENDING_APPROVAL"
    )
    approved = admin.post(
        f"/api/v1/admin/payroll-approvals/{version_id}/decision",
        headers=_csrf(admin),
        json={"approved": True, "note": "批准"},
    )
    assert approved.status_code == 200

    batch = finance.post(
        "/api/v1/finance/payroll-calculations",
        headers=_csrf(finance),
        json={
            "rule_version_id": version_id,
            "period_start": "2026-07-01",
            "period_end": "2026-07-31",
        },
    ).json()
    assert manager_a.get("/api/v1/plant/payroll").json()["items"] == []
    finance.post(
        f"/api/v1/finance/payroll-calculations/{batch['batch_id']}/confirm",
        headers=_csrf(finance),
    )

    assert manager_a.get("/api/v1/plant/payroll").json()["items"][0]["amount"] == "20.00"
    assert manager_b.get("/api/v1/plant/payroll").json()["items"] == []
    assert admin.get("/api/v1/admin/payroll").json()["items"][0]["employee_code"] == "E001"
    assert finance.get("/api/v1/finance/payroll").json()["items"][0]["employee_code"] == "E001"
