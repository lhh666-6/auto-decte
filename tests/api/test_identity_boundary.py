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
        )
    )
    client = TestClient(create_app(services))

    response = client.get(
        "/api/v1/me",
        headers={"X-Actor-ID": "forged-admin", "X-Roles": "ADMIN"},
    )

    assert response.status_code == 200
    assert response.json() == {"actor_id": "local-operator", "roles": ["OPERATOR"]}
