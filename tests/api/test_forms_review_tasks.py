from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.services.container import Services, build_services
from config.settings import Settings


def build_client(tmp_path: Path) -> tuple[TestClient, Services]:
    services = build_services(Settings(data_root=tmp_path))
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    services.imports.import_image(image, "FORM-1", "T1", "1", "operator-a")
    return TestClient(create_app(services), raise_server_exceptions=False), services


def test_operator_gets_403_when_confirming(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)

    response = client.post(
        "/api/v1/forms/FORM-1/confirm",
        headers={"X-Actor-ID": "operator-a", "X-Roles": "OPERATOR"},
        json={
            "expected_version": 0,
            "lease_token": "unused",
            "values": {"total_quantity": 10},
            "reason": "initial confirmation",
            "evidence_ids": [],
        },
    )

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"


def test_reviewer_acquires_lease_and_stale_confirm_returns_409(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)
    headers = {"X-Actor-ID": "reviewer-a", "X-Roles": "REVIEWER"}
    lease = client.post("/api/v1/forms/FORM-1/review-lease", headers=headers).json()
    payload = {
        "expected_version": 0,
        "lease_token": lease["lease_token"],
        "values": {"total_quantity": 10},
        "reason": "initial confirmation",
        "evidence_ids": [],
    }

    confirmed = client.post("/api/v1/forms/FORM-1/confirm", headers=headers, json=payload)
    stale = client.post("/api/v1/forms/FORM-1/confirm", headers=headers, json=payload)

    assert confirmed.status_code == 200
    assert stale.status_code == 409
    assert stale.json()["code"] == "REVIEW_VERSION_CONFLICT"


def test_confirm_uses_if_match_as_the_version_precondition(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)
    headers = {"X-Actor-ID": "reviewer-a", "X-Roles": "REVIEWER", "If-Match": '"0"'}
    lease = client.post("/api/v1/forms/FORM-1/review-lease", headers=headers).json()

    response = client.post(
        "/api/v1/forms/FORM-1/confirm",
        headers=headers,
        json={
            "expected_version": 99,
            "lease_token": lease["lease_token"],
            "values": {"total_quantity": 10},
            "reason": "initial confirmation",
            "evidence_ids": [],
        },
    )

    assert response.status_code == 200
    assert response.json()["version"] == 1


def test_task_creation_returns_accepted_urls_and_is_idempotent(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)
    headers = {
        "X-Actor-ID": "operator-a",
        "X-Roles": "OPERATOR",
        "Idempotency-Key": "recognize-form-1",
    }
    body = {"operation": "FORM_RECOGNITION", "resource_id": "FORM-1", "payload": {"mode": "full"}}

    first = client.post("/api/v1/tasks", headers=headers, json=body)
    second = client.post("/api/v1/tasks", headers=headers, json=body)

    assert first.status_code == 202
    assert first.json()["task_id"] == second.json()["task_id"]
    assert first.json()["events_url"].endswith("/events")
