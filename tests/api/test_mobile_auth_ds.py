"""Production mobile authentication API tests."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services, build_services
from config.settings import Settings


def _services(tmp_path: Path) -> Services:
    services = build_services(Settings(data_root=tmp_path))
    services.master_data.create(
        MasterDataCatalog.EMPLOYEES,
        "E10001",
        "测试员工",
        {},
        "test",
        "identity fixture",
    )
    services.mobile_identity_repository.set_credential("E10001", "2468")
    services.mobile_identity_repository.set_access_profile(
        "E10001",
        team_id="TEAM-A",
        team_name="测试班组",
        position="操作工",
        roles=["WORKER"],
        allowed_form_types=["SHEET_PIECE_MEASUREMENT"],
        allowed_processes=["CUTTING"],
    )
    return services


def test_mobile_router_has_no_process_local_business_store() -> None:
    import app.api.routers.mobile_ds as mobile

    forbidden = {
        "_users",
        "_sessions",
        "_form_schemas",
        "_drafts",
        "_submissions",
        "_outbox",
    }
    assert forbidden.isdisjoint(vars(mobile))


def test_login_uses_httponly_cookie_and_does_not_return_token(tmp_path: Path) -> None:
    client = TestClient(create_app(_services(tmp_path)))

    response = client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": "E10001", "pin": "2468", "device_id": "device-a"},
    )

    assert response.status_code == 200
    assert "token" not in response.json()
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=lax" in response.headers["set-cookie"]
    session = client.get("/api/v1/mobile/auth/session")
    assert session.status_code == 200
    assert session.json()["employee_code"] == "E10001"


def test_logout_revokes_server_session_and_clears_cookie(tmp_path: Path) -> None:
    client = TestClient(create_app(_services(tmp_path)))
    assert client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": "E10001", "pin": "2468"},
    ).status_code == 200

    response = client.post(
        "/api/v1/mobile/auth/logout",
        headers={"X-CSRF-Token": client.cookies["mobile_csrf"]},
    )

    assert response.status_code == 200
    assert client.get("/api/v1/mobile/auth/session").status_code == 401
