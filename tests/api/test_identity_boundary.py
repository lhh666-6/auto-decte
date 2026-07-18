from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main_ds import create_app
from app.services.container import build_services
from config.settings import Settings


def test_production_identity_does_not_trust_client_role_headers(tmp_path: Path) -> None:
    services = build_services(
        Settings(
            data_root=tmp_path,
            environment="production",
            allow_header_identity=False,
            local_default_user_id="local-operator",
            local_default_roles=("OPERATOR",),
        )
    )
    client = TestClient(create_app(services))

    response = client.get(
        "/api/v1/me",
        headers={"X-Actor-ID": "forged-admin", "X-Roles": "ADMIN"},
    )

    assert response.status_code == 200
    assert response.json() == {"actor_id": "local-operator", "roles": ["OPERATOR"]}


def test_local_full_access_uses_business_endpoints_and_keeps_audit(tmp_path: Path) -> None:
    services = build_services(
        Settings(
            data_root=tmp_path,
            app_auth_mode="local_full_access",
            local_default_user_id="local-operator",
            local_default_roles=("OPERATOR",),
        )
    )
    client = TestClient(create_app(services))

    assert client.get("/api/v1/templates").status_code == 200
    assert client.get("/api/v1/forms/queue/review").status_code == 200
    assert client.get("/api/v1/exports/preview").status_code == 200

    created = client.post(
        "/api/v1/master-data/employees",
        json={
            "code": "E001",
            "display_name": "张三",
            "attributes": {"team": "一班"},
            "reason": "本地建档",
        },
    )
    audit = client.get("/api/v1/master-data/employees/E001/audit")

    assert created.status_code == 201, created.text
    assert audit.status_code == 200, audit.text
    assert audit.json()[0]["event_type"] == "CREATE"
    assert audit.json()[0]["actor_id"] == "local-operator"


def test_explicit_authenticated_identity_keeps_role_restrictions(tmp_path: Path) -> None:
    services = build_services(
        Settings(
            data_root=tmp_path,
            app_auth_mode="authenticated",
            allow_header_identity=True,
        )
    )
    client = TestClient(create_app(services))

    response = client.post(
        "/api/v1/master-data/employees",
        headers={"X-Actor-ID": "operator-a", "X-Roles": "OPERATOR"},
        json={
            "code": "E001",
            "display_name": "张三",
            "attributes": {},
            "reason": "越权建档",
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
    assert "master_data.write" not in response.text
    assert "Actor" not in response.text
