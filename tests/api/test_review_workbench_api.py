from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import (
    Form,
    FormField,
    RecognitionAttempt,
    RecordStatus,
    RecordVersion,
    ReviewStatus,
)
from app.domain.templates_ds import FieldDefinition, FieldRules, PageSpec, Rect, TemplateVersion
from app.modules.templates.payroll_profiles_ds import reviewed_payroll_seed_templates
from app.services.container import Services, build_services
from config.settings import Settings


def build_client(tmp_path: Path) -> tuple[TestClient, Services]:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    image = tmp_path / "scan.png"
    image.write_bytes(b"source-image")
    services.imports.import_image(image, "FORM-1", "T1", "1", "operator-a")
    services.repository.add_form_field(
        FormField(
            field_id="FIELD-1",
            form_id="FORM-1",
            field_name="total_quantity",
            source_region={"x": 10, "y": 20, "width": 80, "height": 30},
            current_value=8,
        )
    )
    evidence = services.repository.list_evidence("FORM-1")[0]
    services.repository.add_recognition_attempt(
        RecognitionAttempt(
            attempt_id="ATTEMPT-1",
            field_id="FIELD-1",
            engine="digits",
            model_version="1",
            candidate_value=8,
            confidence=0.91,
            crop_file_id=evidence.file_id,
        )
    )
    return TestClient(create_app(services), raise_server_exceptions=False), services


def reviewer_headers() -> dict[str, str]:
    return {"X-Actor-ID": "reviewer-a", "X-Roles": "REVIEWER"}


def test_form_workbench_detail_exposes_fields_candidates_and_safe_evidence_url(
    tmp_path: Path,
) -> None:
    client, _ = build_client(tmp_path)

    response = client.get("/api/v1/forms/FORM-1", headers=reviewer_headers())

    assert response.status_code == 200
    payload = response.json()
    assert payload["form"]["form_id"] == "FORM-1"
    assert payload["fields"] == [
        {
            "field_id": "FIELD-1",
            "field_name": "total_quantity",
            "display_name": None,
            "data_type": None,
            "recognition_engine": None,
            "paper_entry_mode": None,
            "recognition_mode": None,
            "fill_policy": None,
            "requires_manual_confirmation": False,
            "review_group": "WORKER",
            "rules": None,
            "source_region": {"x": 10, "y": 20, "width": 80, "height": 30},
            "current_value": 8,
            "current_value_source": None,
            "current_record_version": 0,
            "candidates": [
                {
                    "attempt_id": "ATTEMPT-1",
                    "candidate_value": 8,
                    "confidence": 0.91,
                    "engine": "digits",
                    "model_version": "1",
                    "crop_file_id": payload["evidence"][0]["file_id"],
                }
            ],
        }
    ]
    assert payload["evidence"][0]["download_url"].endswith(
        f"/evidence/{payload['evidence'][0]['file_id']}"
    )
    assert "uri" not in payload["evidence"][0]


def test_workbench_overlays_confirmed_runtime_field_values(tmp_path: Path) -> None:
    client, services = build_client(tmp_path)
    services.repository.add_record_version(
        RecordVersion(
            record_id="RECORD-1",
            form_id="FORM-1",
            version=1,
            previous_version=None,
            status=RecordStatus.CONFIRMED,
            values={"FIELD-1": 12},
            change_reason="人工确认",
            confirmed_by="reviewer-a",
        )
    )
    services.repository.set_review_status("FORM-1", ReviewStatus.CONFIRMED)

    payload = client.get("/api/v1/forms/FORM-1", headers=reviewer_headers()).json()

    assert payload["fields"][0]["current_value"] == 12
    assert payload["fields"][0]["current_value_source"] == "HUMAN_CONFIRMED"
    assert payload["fields"][0]["current_record_version"] == 1


def test_workbench_exposes_template_rules_for_frontend_validation(tmp_path: Path) -> None:
    client, services = build_client(tmp_path)
    page = PageSpec.a4_portrait()
    template = TemplateVersion.draft("TPL-T1", "T1", 1, page)
    template.add_field(
        FieldDefinition(
            field_key="total_quantity",
            display_name="总数量",
            data_type="integer",
            input_type="digit_boxes",
            page=page,
            region=Rect(0.1, 0.1, 0.2, 0.05),
            rules=FieldRules(required=True, minimum_value=0, maximum_value=100),
        )
    )
    template.mark_ready_to_publish()
    template.publish()
    services.template_repository.add_version(template)

    field = client.get("/api/v1/forms/FORM-1", headers=reviewer_headers()).json()["fields"][0]

    assert field["display_name"] == "总数量"
    assert field["data_type"] == "integer"
    assert field["paper_entry_mode"] == "DIGIT_BOXES"
    assert field["recognition_mode"] == "NONE"
    assert field["fill_policy"] == "MANUAL_ONLY"
    assert field["requires_manual_confirmation"] is False
    assert field["review_group"] == "WORKER"
    assert field["rules"] == {
        "required": True,
        "minimum_value": 0.0,
        "maximum_value": 100.0,
        "allowed_values": [],
        "master_data_source": None,
        "master_data_options": [],
    }


def test_payroll_workbench_assigns_fields_to_four_review_roles(tmp_path: Path) -> None:
    client, services = build_client(tmp_path)
    template = reviewed_payroll_seed_templates()[0]
    services.template_repository.add_version(template)
    services.repository.add_form(
        Form(
            "FORM-ROLES",
            template.template_key,
            str(template.version),
            review_status=ReviewStatus.NEEDS_REVIEW,
        )
    )
    selected_fields = {
        "worker_number": "WORKER",
        "assessment_passed": "QUALITY",
        "hourly_rate": "SUPERVISOR",
        "worker_signature": "SIGNATURE",
    }
    for index, field_name in enumerate(selected_fields):
        services.repository.add_form_field(
            FormField(
                f"FORM-ROLES:{field_name}",
                "FORM-ROLES",
                field_name,
                {"x": 10, "y": 10 + index * 20, "width": 80, "height": 15},
            )
        )

    response = client.get("/api/v1/forms/FORM-ROLES", headers=reviewer_headers())

    assert response.status_code == 200
    assert {
        field["field_name"]: field["review_group"] for field in response.json()["fields"]
    } == selected_fields


def test_reviewer_reads_form_evidence_through_controlled_endpoint(tmp_path: Path) -> None:
    client, services = build_client(tmp_path)
    file_id = services.repository.list_evidence("FORM-1")[0].file_id

    response = client.get(f"/api/v1/forms/FORM-1/evidence/{file_id}", headers=reviewer_headers())

    assert response.status_code == 200
    assert response.content == b"source-image"


def test_reviewer_reads_review_history_without_evidence_paths(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)

    response = client.get("/api/v1/forms/FORM-1/review-history", headers=reviewer_headers())

    assert response.status_code == 200
    assert response.json()["versions"] == []
    assert response.json()["audits"][0]["event_type"] == "IMPORT"
    assert "uri" not in response.json()["audits"][0]


def test_reviewer_heartbeats_then_releases_own_review_lease(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)
    headers = reviewer_headers()
    lease = client.post("/api/v1/forms/FORM-1/review-lease", headers=headers).json()

    heartbeat = client.post(
        "/api/v1/forms/FORM-1/review-lease/heartbeat",
        headers=headers,
        json={"lease_token": lease["lease_token"]},
    )
    released = client.request(
        "DELETE",
        "/api/v1/forms/FORM-1/review-lease",
        headers=headers,
        json={"lease_token": lease["lease_token"]},
    )

    assert heartbeat.status_code == 200
    assert heartbeat.json()["lease_token"] == lease["lease_token"]
    assert released.status_code == 204


def test_admin_force_releases_a_held_review_lease(tmp_path: Path) -> None:
    client, _ = build_client(tmp_path)
    client.post("/api/v1/forms/FORM-1/review-lease", headers=reviewer_headers())

    response = client.post(
        "/api/v1/forms/FORM-1/review-lease/force-release",
        headers={"X-Actor-ID": "admin-a", "X-Roles": "ADMIN"},
        json={"reason": "shift handover"},
    )

    assert response.status_code == 204
