from hashlib import sha256
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import ReviewStatus
from app.domain.templates_ds import (
    FieldDefinition,
    PageSpec,
    Rect,
    TemplateVersion,
    build_sheet_payload,
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


def test_duplicate_image_returns_existing_form_without_creating_failed_task(
    tmp_path: Path,
) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    client = TestClient(create_app(services), raise_server_exceptions=False)
    content = _png_bytes(np.full((201, 201), 230, dtype=np.uint8))
    base_headers = {
        "X-Actor-ID": "operator-a",
        "X-Roles": "OPERATOR",
        "Content-Type": "image/png",
    }
    first = client.post(
        "/api/v1/imports",
        headers={**base_headers, "Idempotency-Key": "first-import"},
        content=content,
    )
    second = client.post(
        "/api/v1/imports",
        headers={**base_headers, "Idempotency-Key": "second-import"},
        content=content,
    )

    assert first.status_code == 202
    assert second.status_code == 409
    payload = second.json()
    assert payload["code"] == "DUPLICATE_EVIDENCE"
    assert payload["existing_form"] == {
        "form_id": first.json()["form_id"],
        "review_status": "NEEDS_CLASSIFICATION",
    }
    assert payload["actions"] == {
        "can_open": True,
        "can_reopen_for_test": False,
        "can_purge_for_test": False,
    }
    assert services.task_store.list_by_status("FAILED") == []


def test_development_admin_reopens_voided_form_and_can_purge_it(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    client = TestClient(create_app(services), raise_server_exceptions=False)
    content = _png_bytes(np.full((202, 202), 220, dtype=np.uint8))
    admin_headers = {
        "X-Actor-ID": "admin-a",
        "X-Roles": "ADMIN",
        "Content-Type": "image/png",
        "Idempotency-Key": "admin-import",
    }
    imported = client.post("/api/v1/imports", headers=admin_headers, content=content)
    form_id = imported.json()["form_id"]
    services.repository.set_review_status(form_id, ReviewStatus.VOIDED)

    duplicate = client.post(
        "/api/v1/imports",
        headers={**admin_headers, "Idempotency-Key": "admin-duplicate"},
        content=content,
    )
    assert duplicate.json()["actions"]["can_reopen_for_test"] is True
    assert duplicate.json()["actions"]["can_purge_for_test"] is True

    reopened = client.post(
        f"/api/v1/imports/existing/{form_id}/reopen-test",
        headers={"X-Actor-ID": "admin-a", "X-Roles": "ADMIN"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["review_status"] == "NEEDS_CLASSIFICATION"
    assert services.repository.list_audit_events(form_id)[-1].event_type == (
        "REOPEN_FOR_LOCAL_TEST"
    )
    classification_queue = client.get(
        "/api/v1/forms/queue/classification",
        headers={"X-Actor-ID": "admin-a", "X-Roles": "ADMIN"},
    )
    assert form_id in {item["form_id"] for item in classification_queue.json()}

    original_uri = services.repository.list_evidence(form_id)[0].uri
    purged = client.delete(
        f"/api/v1/imports/existing/{form_id}",
        headers={"X-Actor-ID": "admin-a", "X-Roles": "ADMIN"},
    )
    assert purged.status_code == 200
    assert services.repository.get_form(form_id) is None
    assert not (services.settings.evidence_root / original_uri).exists()


def test_test_admin_routes_are_hidden_outside_development(tmp_path: Path) -> None:
    services = build_services(
        Settings(data_root=tmp_path, allow_header_identity=True, environment="production")
    )
    client = TestClient(create_app(services), raise_server_exceptions=False)

    response = client.delete(
        "/api/v1/imports/existing/FORM-1",
        headers={"X-Actor-ID": "admin-a", "X-Roles": "ADMIN"},
    )

    assert response.status_code == 404


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


def test_import_prioritizes_valid_sheet_identity_when_both_qrs_are_present(
    tmp_path: Path,
) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    template = TemplateVersion.draft("TPL-SHEET", "PAYROLL_HOURLY", 4, PageSpec.a4_portrait())
    template.mark_ready_to_publish()
    template.publish()
    services.template_repository.add_version(template)
    artifact = next(
        item
        for item in services.template_renderer.render(
            template,
            print_batch="PB20260719C",
            sequence=19,
        )
        if item.kind == "PRINT_PNG"
    )
    client = TestClient(create_app(services), raise_server_exceptions=False)

    response = client.post(
        "/api/v1/imports",
        headers={
            "X-Actor-ID": "operator-a",
            "X-Roles": "OPERATOR",
            "Idempotency-Key": "import-sheet-priority",
            "Content-Type": "image/png",
        },
        content=Path(artifact.internal_uri).read_bytes(),
    )

    assert response.status_code == 202
    form_id = response.json()["form_id"]
    imported = services.repository.get_form(form_id)
    classification = next(
        event
        for event in services.repository.list_audit_events(form_id)
        if event.event_type == "CLASSIFY"
    )
    assert imported is not None
    assert (imported.template_id, imported.template_version) == ("PAYROLL_HOURLY", "4")
    assert classification.after["source"] == "SHEET_QR"
    assert classification.after["sheet_reference"] == build_sheet_payload(
        "PB20260719C",
        19,
    )


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


def test_processing_failure_marks_task_failed_and_removes_partial_form(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    page = PageSpec.a4_portrait()
    template = TemplateVersion.draft("TPL-FAIL", "PAYROLL_HOURLY", 1, page)
    template.mark_ready_to_publish()
    template.publish()
    services.template_repository.add_version(template)
    artifact = next(
        item for item in services.template_renderer.render(template) if item.kind == "PRINT_PNG"
    )
    content = Path(artifact.internal_uri).read_bytes()

    def fail_crops(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated crop failure")

    monkeypatch.setattr(services.recognition, "record_template_field_crops", fail_crops)
    client = TestClient(create_app(services), raise_server_exceptions=False)
    response = client.post(
        "/api/v1/imports",
        headers={
            "X-Actor-ID": "operator-a",
            "X-Roles": "OPERATOR",
            "Idempotency-Key": "failing-import",
            "Content-Type": "image/png",
        },
        content=content,
    )

    form_id = f"FORM-{sha256(content).hexdigest()[:24]}"
    assert response.status_code == 500
    assert response.json()["code"] == "IMPORT_PROCESSING_FAILED"
    assert services.repository.get_form(form_id) is None
    failed_tasks = services.task_store.list_by_status("FAILED")
    assert len(failed_tasks) == 1
    assert failed_tasks[0].resource_id == form_id
