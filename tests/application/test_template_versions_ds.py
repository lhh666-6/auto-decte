"""Template draft, preflight and publication behavior."""

from app.application.template_versions_ds import TemplateVersions
from app.domain.templates_ds import FieldDefinition, PageSpec, Rect, TemplateStatus, TemplateVersion


class InMemoryTemplateRepository:
    def __init__(self) -> None:
        self.versions: dict[str, TemplateVersion] = {}

    def add_version(self, version: TemplateVersion) -> None:
        self.versions[version.version_id] = version

    def get_version(self, version_id: str) -> TemplateVersion | None:
        return self.versions.get(version_id)

    def replace_version(self, version: TemplateVersion) -> None:
        self.versions[version.version_id] = version

    def list_versions(self, template_key: str) -> list[TemplateVersion]:
        return [
            version for version in self.versions.values() if version.template_key == template_key
        ]


def test_preflight_blocks_field_overlapping_template_qr_safe_zone() -> None:
    service = TemplateVersions(InMemoryTemplateRepository())
    draft = service.create_draft("PAYROLL_HOURLY", PageSpec.a4_portrait())
    service.add_field(
        draft.version_id,
        FieldDefinition(
            "worker_name",
            "姓名",
            "text",
            "text_box",
            Rect(0.82, 0.03, 0.12, 0.08),
            draft.page,
        ),
    )

    report = service.preflight(draft.version_id)

    assert report.ok is False
    assert {issue.code for issue in report.issues} == {"QR_SAFE_ZONE_OVERLAP"}
    assert service.get(draft.version_id).status is TemplateStatus.PREFLIGHT_FAILED


def test_preflight_then_publish_and_clone_preserves_immutable_parent() -> None:
    service = TemplateVersions(InMemoryTemplateRepository())
    draft = service.create_draft("PAYROLL_HOURLY", PageSpec.a4_portrait())
    service.add_field(
        draft.version_id,
        FieldDefinition(
            "worker_name",
            "姓名",
            "text",
            "text_box",
            Rect(0.1, 0.2, 0.2, 0.05),
            draft.page,
        ),
    )

    assert service.preflight(draft.version_id).ok is True
    published = service.publish(draft.version_id)
    clone = service.clone(published.version_id)

    assert published.status is TemplateStatus.PUBLISHED
    assert clone.status is TemplateStatus.DRAFT
    assert clone.version == 2
    assert clone.parent_version_id == published.version_id
    assert [field.field_key for field in clone.fields] == ["worker_name"]


def test_preflight_rejects_incompatible_recognition_engine_and_field_shape() -> None:
    service = TemplateVersions(InMemoryTemplateRepository())
    draft = service.create_draft("PAYROLL_HOURLY", PageSpec.a4_portrait())
    service.add_field(
        draft.version_id,
        FieldDefinition(
            "worker_name",
            "Name",
            "text",
            "text_box",
            Rect(0.1, 0.2, 0.2, 0.05),
            draft.page,
            recognition_engine="digit_template",
        ),
    )

    report = service.preflight(draft.version_id)

    assert {issue.code for issue in report.issues} == {"RECOGNITION_ENGINE_MISMATCH"}
