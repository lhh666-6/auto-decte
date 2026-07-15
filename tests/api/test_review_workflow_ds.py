from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import Form, FormField, RecordStatus, ReviewStatus
from app.domain.templates_ds import (
    FieldDefinition,
    FieldRules,
    PageSpec,
    Rect,
    TemplateVersion,
)
from app.modules.review.repository_ds import SqlAlchemyReviewLeaseRepository
from app.services.container import Services, build_services
from config.settings import Settings


def _headers(role: str = "REVIEWER", actor: str = "reviewer-a") -> dict[str, str]:
    return {"X-Actor-ID": actor, "X-Roles": role}


def _published_template(services: Services) -> TemplateVersion:
    page = PageSpec.a4_portrait()
    template = TemplateVersion.draft("TPL-PAYROLL-1", "PAYROLL_REVIEW", 1, page)
    template.add_field(
        FieldDefinition(
            field_key="work_date",
            display_name="工作日期",
            data_type="text",
            input_type="text",
            page=page,
            region=Rect(0.2, 0.2, 0.2, 0.05),
            rules=FieldRules(required=True),
        )
    )
    template.add_field(
        FieldDefinition(
            field_key="quantity",
            display_name="数量",
            data_type="integer",
            input_type="number",
            page=page,
            region=Rect(0.2, 0.3, 0.2, 0.05),
            rules=FieldRules(minimum_value=0, maximum_value=10),
        )
    )
    template.mark_ready_to_publish()
    template.publish()
    services.template_repository.add_version(template)
    return template


def _add_form(
    services: Services,
    form_id: str,
    *,
    created_at: datetime,
    priority: int = 0,
    status: ReviewStatus = ReviewStatus.NEEDS_REVIEW,
) -> None:
    services.repository.add_form(
        Form(
            form_id,
            "PAYROLL_REVIEW",
            "1",
            review_status=status,
            created_at=created_at,
            priority=priority,
        )
    )
    services.repository.add_form_field(
        FormField(
            field_id=f"{form_id}:work_date",
            form_id=form_id,
            field_name="work_date",
            source_region={"x": 10, "y": 20, "width": 80, "height": 30},
        )
    )
    services.repository.add_form_field(
        FormField(
            field_id=f"{form_id}:quantity",
            form_id=form_id,
            field_name="quantity",
            source_region={"x": 10, "y": 60, "width": 80, "height": 30},
        )
    )


def _client(tmp_path: Path) -> tuple[TestClient, Services]:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    _published_template(services)
    _add_form(services, "FORM-1", created_at=datetime(2026, 7, 15, tzinfo=UTC))
    return TestClient(create_app(services), raise_server_exceptions=False), services


def _lease(client: TestClient, form_id: str = "FORM-1") -> dict[str, object]:
    response = client.post(f"/api/v1/forms/{form_id}/review-lease", headers=_headers())
    assert response.status_code == 200
    return cast(dict[str, object], response.json())


def test_review_draft_is_persisted_without_changing_confirmed_facts(tmp_path: Path) -> None:
    client, services = _client(tmp_path)
    lease = _lease(client)

    saved = client.put(
        "/api/v1/forms/FORM-1/review-draft",
        headers=_headers(),
        json={
            "expected_version": 0,
            "lease_token": lease["lease_token"],
            "values": {"FORM-1:work_date": "2026-07-15"},
        },
    )
    detail = client.get("/api/v1/forms/FORM-1", headers=_headers())

    assert saved.status_code == 200
    assert saved.json()["saved_by"] == "reviewer-a"
    assert detail.json()["draft"]["values"] == {"FORM-1:work_date": "2026-07-15"}
    assert services.repository.get_form("FORM-1").current_record_version == 0  # type: ignore[union-attr]
    assert services.repository.list_record_versions("FORM-1") == []
    assert services.repository.list_audit_events("FORM-1")[-1].event_type == "SAVE_DRAFT"


def test_return_requires_lease_and_reason_then_clears_draft_atomically(tmp_path: Path) -> None:
    client, services = _client(tmp_path)
    lease = _lease(client)
    body = {
        "expected_version": 0,
        "lease_token": lease["lease_token"],
        "values": {"FORM-1:work_date": "2026-07-15"},
    }
    client.put("/api/v1/forms/FORM-1/review-draft", headers=_headers(), json=body)

    returned = client.post(
        "/api/v1/forms/FORM-1/return",
        headers=_headers(),
        json={
            "expected_version": 0,
            "lease_token": lease["lease_token"],
            "reason": "原图无法辨认，请重新拍摄",
            "evidence_ids": [],
        },
    )

    assert returned.status_code == 200
    assert returned.json()["review_status"] == "RECAPTURE_REQUIRED"
    assert services.repository.get_form("FORM-1").review_status is ReviewStatus.RECAPTURE_REQUIRED  # type: ignore[union-attr]
    assert services.review_repository.get_draft("FORM-1") is None
    assert SqlAlchemyReviewLeaseRepository(services.engine).get("FORM-1") is None
    event = services.repository.list_audit_events("FORM-1")[-1]
    assert (event.event_type, event.reason) == ("RETURN", "原图无法辨认，请重新拍摄")


def test_void_appends_a_voided_version_and_preserves_the_reason(tmp_path: Path) -> None:
    client, services = _client(tmp_path)
    lease = _lease(client)
    client.put(
        "/api/v1/forms/FORM-1/review-draft",
        headers=_headers(),
        json={
            "expected_version": 0,
            "lease_token": lease["lease_token"],
            "values": {"FORM-1:work_date": "2026-07-15"},
        },
    )

    voided = client.post(
        "/api/v1/forms/FORM-1/void",
        headers=_headers(),
        json={
            "expected_version": 0,
            "lease_token": lease["lease_token"],
            "reason": "重复上传的作废表单",
            "evidence_ids": [],
        },
    )

    versions = services.repository.list_record_versions("FORM-1")
    assert voided.status_code == 200
    assert voided.json()["status"] == "VOIDED"
    assert versions[-1].status is RecordStatus.VOIDED
    assert versions[-1].values == {"FORM-1:work_date": "2026-07-15"}
    assert services.repository.get_form("FORM-1").review_status is ReviewStatus.VOIDED  # type: ignore[union-attr]
    assert services.repository.list_audit_events("FORM-1")[-1].reason == "重复上传的作废表单"


def test_confirm_and_claim_next_uses_priority_and_stable_created_order(tmp_path: Path) -> None:
    client, services = _client(tmp_path)
    base = datetime(2026, 7, 15, tzinfo=UTC)
    _add_form(services, "FORM-LATER", created_at=base + timedelta(minutes=2), priority=10)
    _add_form(services, "FORM-EARLIER", created_at=base + timedelta(minutes=1), priority=10)
    _add_form(services, "FORM-LOW", created_at=base - timedelta(minutes=1), priority=1)
    _add_form(services, "FORM-HELD", created_at=base, priority=100)
    held = client.post(
        "/api/v1/forms/FORM-HELD/review-lease",
        headers=_headers(actor="reviewer-b"),
    )
    assert held.status_code == 200
    lease = _lease(client)

    response = client.post(
        "/api/v1/forms/FORM-1/confirm-and-claim-next",
        headers=_headers(),
        json={
            "expected_version": 0,
            "lease_token": lease["lease_token"],
            "values": {
                "FORM-1:work_date": "2026-07-15",
                "FORM-1:quantity": "8",
            },
            "reason": "人工复核确认",
            "evidence_ids": [],
            "queue_key": "review",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["record"]["version"] == 1
    assert services.repository.list_record_versions("FORM-1")[-1].values[
        "FORM-1:quantity"
    ] == 8
    assert payload["next"]["workbench"]["form"]["form_id"] == "FORM-EARLIER"
    assert payload["next"]["lease"]["owner_id"] == "reviewer-a"
    assert SqlAlchemyReviewLeaseRepository(services.engine).get("FORM-1") is None
    assert SqlAlchemyReviewLeaseRepository(services.engine).get("FORM-EARLIER") is not None


def test_confirm_and_claim_next_rolls_back_when_template_rules_block_values(
    tmp_path: Path,
) -> None:
    client, services = _client(tmp_path)
    _add_form(
        services,
        "FORM-2",
        created_at=datetime(2026, 7, 15, 0, 1, tzinfo=UTC),
        priority=5,
    )
    lease = _lease(client)

    response = client.post(
        "/api/v1/forms/FORM-1/confirm-and-claim-next",
        headers=_headers(),
        json={
            "expected_version": 0,
            "lease_token": lease["lease_token"],
            "values": {},
            "reason": "人工复核确认",
            "evidence_ids": [],
            "queue_key": "review",
        },
    )

    assert response.status_code == 422
    assert response.json()["code"] == "REVIEW_RULE_BLOCKED"
    assert response.json()["failures"][0]["code"] == "REQUIRED"
    assert services.repository.list_record_versions("FORM-1") == []
    assert SqlAlchemyReviewLeaseRepository(services.engine).get("FORM-1") is not None
    assert SqlAlchemyReviewLeaseRepository(services.engine).get("FORM-2") is None


def test_manual_classification_lists_published_options_and_queues_recognition(
    tmp_path: Path,
) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    _published_template(services)
    draft = TemplateVersion.draft("TPL-DRAFT", "UNPUBLISHED", 1, PageSpec.a4_portrait())
    services.template_repository.add_version(draft)
    services.repository.add_form(
        Form("FORM-CLASSIFY", "UNKNOWN", "0", review_status=ReviewStatus.NEEDS_CLASSIFICATION)
    )
    client = TestClient(create_app(services), raise_server_exceptions=False)

    options = client.get(
        "/api/v1/forms/FORM-CLASSIFY/classification-options",
        headers=_headers("OPERATOR", "operator-a"),
    )
    assigned = client.post(
        "/api/v1/forms/FORM-CLASSIFY/assign-template",
        headers=_headers("OPERATOR", "operator-a"),
        json={"template_key": "PAYROLL_REVIEW", "version": 1, "reason": "二维码污损"},
    )

    assert options.status_code == 200
    assert [(item["template_key"], item["version"]) for item in options.json()] == [
        ("PAYROLL_REVIEW", 1)
    ]
    assert assigned.status_code == 200
    task = services.tasks.get(assigned.json()["recognition_task_id"])
    assert task.operation == "FORM_RECOGNITION"
    assert task.resource_id == "FORM-CLASSIFY"
