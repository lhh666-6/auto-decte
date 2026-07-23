"""Phase 4 Web API role scope, returns and finance review."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.modules.submission_ledger.service_ds import SubmissionLedgerService
from app.services.container import Services, build_services
from config.settings import Settings


def _add_user(
    services: Services, code: str, role: str, factory_id: str = ""
) -> None:
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES, code, code, {}, "phase-4", "fixture"
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
    _add_user(built, "MANAGER-A", "PLANT_MANAGER", "FACTORY-A")
    _add_user(built, "MANAGER-B", "PLANT_MANAGER", "FACTORY-B")
    ledger = SubmissionLedgerService(built.engine)
    for submission_id, factory_id in (("SUB-A", "FACTORY-A"), ("SUB-B", "FACTORY-B")):
        ledger.record_acceptance(
            submission_id=submission_id,
            factory_id=factory_id,
            subject_employee_code=f"WORKER-{factory_id[-1]}",
            actor_id=f"WORKER-{factory_id[-1]}",
            definition_version_id="FORM-V1",
            values={"quantity": 8},
            submitted_at=datetime(2026, 7, 23, tzinfo=UTC),
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


def test_finance_sees_global_ledger_and_period_projection(services: Services) -> None:
    client = _login(services, "FINANCE-1")
    result = client.get("/api/v1/finance/ledger")
    assert result.status_code == 200
    assert {row["factory_id"] for row in result.json()["items"]} == {
        "FACTORY-A",
        "FACTORY-B",
    }
    assert client.get("/api/v1/finance/ledger/overview").json()["year"] == 2


def test_plant_manager_only_sees_and_returns_own_factory(services: Services) -> None:
    manager = _login(services, "MANAGER-A")
    production = manager.get("/api/v1/plant/production")
    assert [row["effective_submission_id"] for row in production.json()["records"]] == [
        "SUB-A"
    ]

    forbidden = manager.post(
        "/api/v1/plant/submissions/SUB-B/return",
        headers=_csrf(manager),
        json={"reason": "跨厂尝试", "assigned_to": "WORKER-B"},
    )
    assert forbidden.status_code == 403

    returned = manager.post(
        "/api/v1/plant/submissions/SUB-A/return",
        headers=_csrf(manager),
        json={"reason": "数量错误", "assigned_to": "WORKER-A"},
    )
    assert returned.status_code == 200
    exceptions = manager.get("/api/v1/plant/exceptions").json()
    assert exceptions["corrections"][0]["status"] == "RETURNED"
    assert exceptions["tasks"][0]["status"] == "PENDING"
