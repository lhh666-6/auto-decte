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
        factory_id="FACTORY-A",
        factory_name="竹丝一厂",
        bamboo_role="SORT_OPERATOR",
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
    assert session.json()["factory_id"] == "FACTORY-A"
    assert session.json()["factory_name"] == "竹丝一厂"
    assert session.json()["bamboo_role"] == "SORT_OPERATOR"


def test_login_exposes_csrf_cookie_to_mobile_page_paths(tmp_path: Path) -> None:
    client = TestClient(create_app(_services(tmp_path)))

    response = client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": "E10001", "pin": "2468", "device_id": "device-a"},
    )

    csrf_cookie = next(
        value
        for value in response.headers.get_list("set-cookie")
        if value.startswith("mobile_csrf=") and "Max-Age=0" not in value
    )
    assert "Path=/;" in csrf_cookie


def test_login_removes_legacy_api_scoped_csrf_cookie(tmp_path: Path) -> None:
    client = TestClient(create_app(_services(tmp_path)))

    response = client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": "E10001", "pin": "2468", "device_id": "device-a"},
    )

    legacy_deletion = next(
        (
            value
            for value in response.headers.get_list("set-cookie")
            if value.startswith('mobile_csrf=""') and "Path=/api/v1/mobile;" in value
        ),
        None,
    )
    assert legacy_deletion is not None
    assert "Max-Age=0" in legacy_deletion


def test_session_refresh_migrates_legacy_csrf_cookie(tmp_path: Path) -> None:
    client = TestClient(create_app(_services(tmp_path)))
    assert client.post(
        "/api/v1/mobile/auth/login",
        json={"employee_code": "E10001", "pin": "2468", "device_id": "device-a"},
    ).status_code == 200
    client.cookies.delete("mobile_csrf")
    client.cookies.set("mobile_csrf", "legacy-token", path="/api/v1/mobile")

    response = client.get("/api/v1/mobile/auth/session")

    assert response.status_code == 200
    refreshed_cookie = next(
        (
            value
            for value in response.headers.get_list("set-cookie")
            if value.startswith("mobile_csrf=") and "Max-Age=0" not in value
        ),
        None,
    )
    assert refreshed_cookie is not None
    assert "Path=/;" in refreshed_cookie


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
