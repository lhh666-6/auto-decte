"""Template management API behavior."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.services.container import build_services
from config.settings import Settings


def _headers() -> dict[str, str]:
    return {"X-Actor-ID": "admin-a", "X-Roles": "ADMIN"}


def _client(tmp_path: Path) -> TestClient:
    return TestClient(
        create_app(build_services(Settings(data_root=tmp_path, allow_header_identity=True))),
        raise_server_exceptions=False,
    )


def _field(display_name: str = "Worker name") -> dict[str, object]:
    return {
        "field_key": "worker_name",
        "display_name": display_name,
        "data_type": "text",
        "input_type": "text_box",
        "recognition_engine": "manual",
        "minimum_prefill_confidence": 0.98,
        "region": {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.05},
    }


def _published_template(client: TestClient) -> str:
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_HOURLY", "page_size": "A4"},
    )
    version_id = created.json()["version_id"]
    client.post(f"/api/v1/template-versions/{version_id}/fields", headers=_headers(), json=_field())
    client.post(f"/api/v1/template-versions/{version_id}/preflight", headers=_headers())
    client.post(f"/api/v1/template-versions/{version_id}/publish", headers=_headers())
    return version_id


def test_admin_creates_preflights_publishes_and_downloads_template_artifact(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_HOURLY", "page_size": "A4"},
    )

    assert created.status_code == 201
    version_id = created.json()["version_id"]
    added = client.post(
        f"/api/v1/template-versions/{version_id}/fields", headers=_headers(), json=_field()
    )
    preflight = client.post(f"/api/v1/template-versions/{version_id}/preflight", headers=_headers())
    published = client.post(f"/api/v1/template-versions/{version_id}/publish", headers=_headers())

    assert added.status_code == 200
    assert added.json()["fields"] == [_field()]
    assert preflight.json()["ok"] is True
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED"
    artifact = published.json()["artifacts"][0]
    download = client.get(artifact["download_url"], headers=_headers())
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("image/")
    assert "internal_uri" not in repr(published.json())


def test_admin_can_list_read_clone_patch_and_delete_template_draft(tmp_path: Path) -> None:
    client = _client(tmp_path)
    version_id = _published_template(client)

    library = client.get("/api/v1/templates", headers=_headers())
    detail = client.get(f"/api/v1/template-versions/{version_id}", headers=_headers())
    clone = client.post(f"/api/v1/template-versions/{version_id}/clone", headers=_headers())
    clone_id = clone.json()["version_id"]
    clone_detail = client.get(f"/api/v1/template-versions/{clone_id}", headers=_headers())
    patched_field = _field("Employee name")
    patched_field["region"] = {"x": 0.15, "y": 0.2, "width": 0.2, "height": 0.05}
    patched_field["minimum_prefill_confidence"] = 0.95
    patched = client.patch(
        f"/api/v1/template-versions/{clone_id}/fields/worker_name",
        headers=_headers(),
        json=patched_field,
    )
    deleted = client.delete(
        f"/api/v1/template-versions/{clone_id}/fields/worker_name", headers=_headers()
    )

    assert library.status_code == 200
    assert library.json()[0]["template_key"] == "PAYROLL_HOURLY"
    assert library.json()[0]["version_id"] == version_id
    assert library.json()[0]["current_published_version"] == 1
    assert library.json()[0]["status"] == "PUBLISHED"
    assert library.json()[0]["page"]["size"] == "A4"
    assert library.json()[0]["field_count"] == 1
    assert detail.status_code == 200
    assert detail.json()["parent_version_id"] is None
    assert detail.json()["page"]["size"] == "A4"
    assert detail.json()["page"]["orientation"] == "portrait"
    assert detail.json()["fields"] == [_field()]
    assert detail.json()["artifacts"]
    assert "internal_uri" not in repr(detail.json())
    assert clone.status_code == 201
    assert clone.json()["status"] == "DRAFT"
    assert clone.json()["parent_version_id"] == version_id
    assert clone_detail.status_code == 200
    assert clone_detail.json()["artifacts"] == []
    assert {artifact["artifact_id"] for artifact in clone_detail.json()["artifacts"]}.isdisjoint(
        {artifact["artifact_id"] for artifact in detail.json()["artifacts"]}
    )
    assert patched.status_code == 200
    assert patched.json()["fields"] == [patched_field]
    assert deleted.status_code == 200
    assert deleted.json()["fields"] == []


def test_template_library_exposes_latest_editable_draft_alongside_published_version(tmp_path: Path) -> None:
    client = _client(tmp_path)
    published_id = _published_template(client)
    clone = client.post(f"/api/v1/template-versions/{published_id}/clone", headers=_headers())

    library = client.get("/api/v1/templates", headers=_headers())

    assert clone.status_code == 201
    assert library.status_code == 200
    assert library.json()[0]["version_id"] == published_id
    assert library.json()[0]["active_draft"] == {
        "version_id": clone.json()["version_id"],
        "version": 2,
        "status": "DRAFT",
        "field_count": 1,
    }


def test_template_library_api_maps_lifecycle_missing_and_permission_errors(tmp_path: Path) -> None:
    client = _client(tmp_path)
    version_id = _published_template(client)

    immutable = client.patch(
        f"/api/v1/template-versions/{version_id}/fields/worker_name",
        headers=_headers(),
        json=_field("Employee name"),
    )
    missing = client.get("/api/v1/template-versions/TPL-MISSING", headers=_headers())
    forbidden = client.get(
        "/api/v1/templates", headers={"X-Actor-ID": "operator-a", "X-Roles": "OPERATOR"}
    )

    assert immutable.status_code == 409
    assert immutable.json()["code"] == "INVALID_LIFECYCLE"
    assert missing.status_code == 404
    assert missing.json()["code"] == "TEMPLATE_VERSION_NOT_FOUND"
    assert forbidden.status_code == 403


def test_template_field_payload_validation_uses_invalid_field_problem_code(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_HOURLY", "page_size": "A4"},
    )
    invalid_field = _field()
    invalid_field["minimum_prefill_confidence"] = -0.1

    response = client.post(
        f"/api/v1/template-versions/{created.json()['version_id']}/fields",
        headers=_headers(),
        json=invalid_field,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_FIELD"


def test_template_field_routes_declare_openapi_request_bodies(tmp_path: Path) -> None:
    schema = _client(tmp_path).app.openapi()

    fields_path = "/api/v1/template-versions/{version_id}/fields"
    field_path = "/api/v1/template-versions/{version_id}/fields/{field_key}"
    assert "requestBody" in schema["paths"][fields_path]["post"]
    assert "requestBody" in schema["paths"][field_path]["patch"]


def test_template_field_routes_return_field_not_found_for_unknown_fields(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_HOURLY", "page_size": "A4"},
    )
    version_id = created.json()["version_id"]
    missing_field = _field()
    missing_field["field_key"] = "missing_field"

    patched = client.patch(
        f"/api/v1/template-versions/{version_id}/fields/missing_field",
        headers=_headers(),
        json=missing_field,
    )
    deleted = client.delete(
        f"/api/v1/template-versions/{version_id}/fields/missing_field", headers=_headers()
    )

    assert patched.status_code == 404
    assert patched.json()["code"] == "FIELD_NOT_FOUND"
    assert deleted.status_code == 404
    assert deleted.json()["code"] == "FIELD_NOT_FOUND"
