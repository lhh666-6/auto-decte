from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.services.container import build_services
from config.settings import Settings


def build_client(tmp_path: Path, *, raise_server_exceptions: bool = True) -> TestClient:
    return TestClient(
        create_app(build_services(Settings(data_root=tmp_path))),
        raise_server_exceptions=raise_server_exceptions,
    )


def test_live_health_returns_request_id(tmp_path: Path) -> None:
    client = build_client(tmp_path)

    response = client.get("/health/live", headers={"X-Request-ID": "REQ-test"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "REQ-test"
    assert response.json() == {"status": "live"}


def test_ready_and_identity_expose_local_capabilities(tmp_path: Path) -> None:
    client = build_client(tmp_path)

    ready = client.get("/health/ready")
    identity = client.get("/api/v1/me")

    assert ready.status_code == 200
    assert ready.json()["capabilities"]["ai"] is False
    assert identity.json()["actor_id"] == "local-operator"
    assert identity.json()["roles"] == ["OPERATOR"]


def test_unhandled_error_uses_problem_details_without_traceback(tmp_path: Path) -> None:
    client = build_client(tmp_path, raise_server_exceptions=False)
    client.app.add_api_route("/test/fail", lambda: 1 / 0)

    response = client.get("/test/fail")

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    assert "traceback" not in response.text.lower()
