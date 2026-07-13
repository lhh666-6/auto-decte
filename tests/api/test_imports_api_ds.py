from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import ReviewStatus
from app.domain.templates_ds import (
    FieldDefinition,
    PageSpec,
    Rect,
    TemplateVersion,
    build_template_payload,
)
from app.services.container import build_services
from config.settings import Settings


def _png_bytes(image: np.ndarray) -> bytes:
    encoded, content = cv2.imencode(".png", image)
    assert encoded
    return content.tobytes()


def test_operator_uploads_image_bytes_into_a_form_import_task(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    client = TestClient(
        create_app(services),
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
        content=_png_bytes(np.full((200, 200), 255, dtype=np.uint8)),
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["operation"] == "FORM_IMPORT"
    assert payload["status"] == "SUCCEEDED"
    assert payload["status_url"].startswith("/api/v1/tasks/")
    assert "form_id" in payload
    imported = services.repository.get_form(payload["form_id"])
    assert imported is not None
    assert imported.review_status is ReviewStatus.NEEDS_CLASSIFICATION


def test_repeated_idempotency_key_returns_the_original_import_task(tmp_path: Path) -> None:
    client = TestClient(
        create_app(build_services(Settings(data_root=tmp_path, allow_header_identity=True))),
        raise_server_exceptions=False,
    )
    headers = {
        "X-Actor-ID": "operator-a",
        "X-Roles": "OPERATOR",
        "Idempotency-Key": "import-retry-001",
        "Content-Type": "image/png",
    }

    content = _png_bytes(np.full((200, 200), 255, dtype=np.uint8))
    first = client.post("/api/v1/imports", headers=headers, content=content)
    second = client.post("/api/v1/imports", headers=headers, content=content)

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["task_id"] == first.json()["task_id"]
    assert second.json()["form_id"] == first.json()["form_id"]


def test_import_binds_only_the_exact_published_template_from_its_qr(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    template = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 3, PageSpec.a4_portrait())
    template.mark_ready_to_publish()
    template.publish()
    services.template_repository.add_version(template)
    client = TestClient(create_app(services), raise_server_exceptions=False)
    qr = cv2.QRCodeEncoder_create().encode(build_template_payload("PAYROLL_HOURLY", 3))

    response = client.post(
        "/api/v1/imports",
        headers={
            "X-Actor-ID": "operator-a",
            "X-Roles": "OPERATOR",
            "Idempotency-Key": "import-qr-001",
            "Content-Type": "image/png",
        },
        content=_png_bytes(qr),
    )

    assert response.status_code == 202
    imported = services.repository.get_form(response.json()["form_id"])
    assert imported is not None
    assert (imported.template_id, imported.template_version) == ("PAYROLL_HOURLY", "3")
    assert imported.review_status is ReviewStatus.CLASSIFIED


def test_import_rejects_invalid_image_bytes_despite_png_content_type(
    tmp_path: Path,
) -> None:
    client = TestClient(
        create_app(build_services(Settings(data_root=tmp_path, allow_header_identity=True))),
        raise_server_exceptions=False,
    )

    response = client.post(
        "/api/v1/imports",
        headers={
            "X-Actor-ID": "operator-a",
            "X-Roles": "OPERATOR",
            "Idempotency-Key": "import-invalid-image",
            "Content-Type": "image/png",
        },
        content=b"not-an-image",
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_IMAGE_CONTENT"


def test_generated_template_print_runs_the_full_correction_and_crop_path(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    page = PageSpec.a4_portrait()
    template = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, page)
    template.add_field(
        FieldDefinition(
            "total_quantity",
            "Total",
            "integer",
            "digit_boxes",
            Rect(0.1, 0.2, 0.2, 0.05),
            page,
            recognition_engine="digit_template",
        )
    )
    template.mark_ready_to_publish()
    template.publish()
    services.template_repository.add_version(template)
    print_artifact = next(
        item for item in services.template_renderer.render(template) if item.kind == "PRINT_PNG"
    )
    client = TestClient(create_app(services), raise_server_exceptions=False)

    response = client.post(
        "/api/v1/imports",
        headers={
            "X-Actor-ID": "operator-a",
            "X-Roles": "OPERATOR",
            "Idempotency-Key": "import-full-print",
            "Content-Type": "image/png",
        },
        content=Path(print_artifact.internal_uri).read_bytes(),
    )

    assert response.status_code == 202
    form_id = response.json()["form_id"]
    evidence_types = {item.type for item in services.repository.list_evidence(form_id)}
    assert {"ORIGINAL_IMAGE", "CORRECTED_IMAGE", "FIELD_CROP"} <= evidence_types
    field = services.repository.list_form_fields(form_id)[0]
    assert services.repository.list_recognition_attempts(field.field_id)
