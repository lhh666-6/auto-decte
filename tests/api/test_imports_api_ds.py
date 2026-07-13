from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.services.container import build_services
from config.settings import Settings


def test_operator_uploads_image_bytes_into_a_form_import_task(tmp_path: Path) -> None:
    client = TestClient(
        create_app(build_services(Settings(data_root=tmp_path, allow_header_identity=True))),
        raise_server_exceptions=False,
    )

    response = client.post(
        "/api/v1/imports",
        headers={
            "X-Actor-ID": "operator-a",
            "X-Roles": "OPERATOR",
            "Idempotency-Key": "import-001",
            "Content-Type": "image/png",
        },
        content=b"not-a-real-png-but-evidence-bytes",
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["operation"] == "FORM_IMPORT"
    assert payload["status"] == "SUCCEEDED"
    assert payload["status_url"].startswith("/api/v1/tasks/")
    assert "form_id" in payload
