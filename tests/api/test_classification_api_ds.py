from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import create_app
from app.domain.models import Form, ReviewStatus
from app.domain.templates_ds import PageSpec, TemplateVersion
from app.services.container import build_services
from config.settings import Settings


def test_operator_assigns_only_a_published_template_to_unclassified_form(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    form = Form("FORM-1", "UNKNOWN", "0", review_status=ReviewStatus.NEEDS_CLASSIFICATION)
    services.repository.add_form(form)
    version = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    version.mark_ready_to_publish()
    version.publish()
    services.template_repository.add_version(version)
    client = TestClient(create_app(services), raise_server_exceptions=False)

    response = client.post(
        "/api/v1/forms/FORM-1/assign-template",
        headers={"X-Actor-ID": "operator-a", "X-Roles": "OPERATOR"},
        json={"template_key": "PAYROLL_HOURLY", "version": 1, "reason": "damaged QR"},
    )

    assert response.status_code == 200
    updated_form = services.repository.get_form("FORM-1")
    assert updated_form is not None
    assert updated_form.review_status is ReviewStatus.CLASSIFIED
    assert services.repository.list_audit_events("FORM-1")[-1].event_type == "RECLASSIFY"


def test_operator_cannot_assign_an_unpublished_template(tmp_path: Path) -> None:
    services = build_services(Settings(data_root=tmp_path, allow_header_identity=True))
    services.repository.add_form(
        Form("FORM-1", "UNKNOWN", "0", review_status=ReviewStatus.NEEDS_CLASSIFICATION)
    )
    draft = TemplateVersion.draft("TPL-1", "PAYROLL_HOURLY", 1, PageSpec.a4_portrait())
    services.template_repository.add_version(draft)
    client = TestClient(create_app(services), raise_server_exceptions=False)

    response = client.post(
        "/api/v1/forms/FORM-1/assign-template",
        headers={"X-Actor-ID": "operator-a", "X-Roles": "OPERATOR"},
        json={"template_key": "PAYROLL_HOURLY", "version": 1, "reason": "damaged QR"},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "TEMPLATE_VERSION_NOT_PUBLISHED"
