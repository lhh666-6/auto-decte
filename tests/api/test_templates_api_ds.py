"""Template management API behavior."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.services.container import build_services
from config.settings import Settings


def _headers() -> dict[str, str]:
    return {"X-Actor-ID": "admin-a", "X-Roles": "ADMIN"}


def test_admin_creates_preflights_publishes_and_downloads_template_artifact(tmp_path: Path) -> None:
    client = TestClient(
        create_app(build_services(Settings(data_root=tmp_path, allow_header_identity=True))),
        raise_server_exceptions=False,
    )
    created = client.post(
        "/api/v1/templates",
        headers=_headers(),
        json={"template_key": "PAYROLL_HOURLY", "page_size": "A4"},
    )

    assert created.status_code == 201
    version_id = created.json()["version_id"]
    added = client.post(
        f"/api/v1/template-versions/{version_id}/fields",
        headers=_headers(),
        json={
            "field_key": "worker_name",
            "display_name": "姓名",
            "data_type": "text",
            "input_type": "text_box",
            "region": {"x": 0.1, "y": 0.2, "width": 0.2, "height": 0.05},
        },
    )
    preflight = client.post(f"/api/v1/template-versions/{version_id}/preflight", headers=_headers())
    published = client.post(f"/api/v1/template-versions/{version_id}/publish", headers=_headers())

    assert added.status_code == 200
    assert preflight.json()["ok"] is True
    assert published.status_code == 200
    assert published.json()["status"] == "PUBLISHED"
    artifact = published.json()["artifacts"][0]
    download = client.get(artifact["download_url"], headers=_headers())
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("image/")
    assert "internal_uri" not in repr(published.json())
