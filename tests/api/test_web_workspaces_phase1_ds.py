"""Phase 1 Web authentication, role routing, and factory isolation."""

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
    factory_name: str = "",
) -> None:
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES,
        employee_code,
        employee_code,
        {},
        "phase-1-test",
        "web workspace fixture",
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
        factory_name=factory_name,
        bamboo_role="",
    )


@pytest.fixture()
def services(tmp_path: Path) -> Services:
    built = build_services(Settings(data_root=tmp_path))
    _add_user(built, "ADMIN-1", "ADMIN")
    _add_user(built, "FINANCE-1", "FINANCE")
    _add_user(
        built,
        "MANAGER-A",
        "PLANT_MANAGER",
        factory_id="FACTORY-A",
        factory_name="竹丝一厂",
    )
    _add_user(
        built,
        "MANAGER-B",
        "PLANT_MANAGER",
        factory_id="FACTORY-B",
        factory_name="竹丝二厂",
    )
    _add_user(built, "WORKER-1", "WORKER", factory_id="FACTORY-A")
    return built


def _login(services: Services, employee_code: str) -> TestClient:
    client = TestClient(create_app(services))
    result = client.post(
        "/api/v1/web/auth/login",
        json={
            "employee_code": employee_code,
            "pin": "2468",
            "device_id": f"{employee_code}-browser",
        },
    )
    assert result.status_code == 200, result.text
    return client


def test_web_login_reuses_employee_account_and_selects_role_landing(
    services: Services,
) -> None:
    expected = {
        "ADMIN-1": ("ADMIN", "/admin/overview"),
        "FINANCE-1": ("FINANCE", "/finance/overview"),
        "MANAGER-A": ("PLANT_MANAGER", "/plant/overview"),
    }

    for employee_code, (workspace_role, landing_path) in expected.items():
        client = _login(services, employee_code)
        session = client.get("/api/v1/web/auth/session")

        assert session.status_code == 200
        assert session.json()["employee_code"] == employee_code
        assert session.json()["workspace_role"] == workspace_role
        assert session.json()["landing_path"] == landing_path
        assert "web_session" in client.cookies
        assert "web_csrf" in client.cookies
        assert "token" not in session.json()


def test_line_worker_cannot_create_web_management_session(services: Services) -> None:
    client = TestClient(create_app(services))
    result = client.post(
        "/api/v1/web/auth/login",
        json={"employee_code": "WORKER-1", "pin": "2468", "device_id": "browser"},
    )

    assert result.status_code == 403
    assert result.json()["code"] == "WEB_ROLE_REQUIRED"
    assert "web_session" not in client.cookies


@pytest.mark.parametrize(
    ("employee_code", "allowed_path", "forbidden_paths"),
    [
        (
            "ADMIN-1",
            "/api/v1/admin/overview",
            [],
        ),
        (
            "FINANCE-1",
            "/api/v1/finance/overview",
            ["/api/v1/admin/overview", "/api/v1/plant/overview"],
        ),
        (
            "MANAGER-A",
            "/api/v1/plant/overview",
            ["/api/v1/admin/overview", "/api/v1/finance/overview"],
        ),
    ],
)
def test_server_enforces_three_workspace_role_matrix(
    services: Services,
    employee_code: str,
    allowed_path: str,
    forbidden_paths: list[str],
) -> None:
    client = _login(services, employee_code)

    assert client.get(allowed_path).status_code == 200
    for path in forbidden_paths:
        denied = client.get(path)
        assert denied.status_code == 403
        assert denied.json()["code"] == "WEB_ROLE_FORBIDDEN"


def test_admin_has_highest_access_to_all_workspaces(services: Services) -> None:
    client = _login(services, "ADMIN-1")

    assert client.get("/api/v1/admin/overview").status_code == 200
    assert client.get("/api/v1/finance/overview").status_code == 200
    plant = client.get("/api/v1/plant/overview", params={"factory_id": "FACTORY-B"})
    assert plant.status_code == 200
    assert plant.json()["factory_id"] == "FACTORY-B"


def test_plant_manager_is_restricted_to_own_factory(services: Services) -> None:
    client = _login(services, "MANAGER-A")

    own = client.get("/api/v1/plant/overview")
    assert own.status_code == 200
    assert own.json()["factory_id"] == "FACTORY-A"
    assert own.json()["factory_name"] == "竹丝一厂"

    other = client.get("/api/v1/plant/overview", params={"factory_id": "FACTORY-B"})
    assert other.status_code == 403
    assert other.json()["code"] == "CROSS_FACTORY_FORBIDDEN"


def test_finance_can_filter_global_overview_by_factory(services: Services) -> None:
    client = _login(services, "FINANCE-1")

    overview = client.get(
        "/api/v1/finance/overview",
        params={"factory_id": "FACTORY-B"},
    )
    assert overview.status_code == 200
    assert overview.json()["scope"] == "GLOBAL"
    assert overview.json()["factory_id"] == "FACTORY-B"


def test_web_logout_requires_csrf_and_revokes_session(services: Services) -> None:
    client = _login(services, "MANAGER-A")

    denied = client.post("/api/v1/web/auth/logout")
    assert denied.status_code == 403
    logged_out = client.post(
        "/api/v1/web/auth/logout",
        headers={"X-CSRF-Token": client.cookies["web_csrf"]},
    )
    assert logged_out.status_code == 200
    assert client.get("/api/v1/web/auth/session").status_code == 401


def test_workspace_endpoints_require_web_session(services: Services) -> None:
    client = TestClient(create_app(services))

    for path in (
        "/api/v1/admin/overview",
        "/api/v1/finance/overview",
        "/api/v1/plant/overview",
    ):
        response = client.get(path)
        assert response.status_code == 401
        assert response.json()["code"] == "WEB_SESSION_REQUIRED"
