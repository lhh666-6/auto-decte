"""Template draft, preflight, publication and cloning use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from app.domain.templates_ds import FieldDefinition, PageSpec, Rect, TemplateStatus, TemplateVersion

_TEMPLATE_QR_SAFE_ZONE = Rect(0.80, 0.02, 0.16, 0.12)


class TemplateVersionRepository(Protocol):
    def add_version(self, version: TemplateVersion) -> None: ...

    def get_version(self, version_id: str) -> TemplateVersion | None: ...

    def replace_version(self, version: TemplateVersion) -> None: ...

    def list_versions(self, template_key: str) -> list[TemplateVersion]: ...


@dataclass(frozen=True, slots=True)
class PreflightIssue:
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class PreflightReport:
    issues: tuple[PreflightIssue, ...]

    @property
    def ok(self) -> bool:
        return not self.issues


class TemplateVersions:
    """Own template-version lifecycle transitions outside the UI layer."""

    def __init__(self, repository: TemplateVersionRepository) -> None:
        self._repository = repository

    def create_draft(self, template_key: str, page: PageSpec) -> TemplateVersion:
        prior_versions = self._repository.list_versions(template_key)
        next_version = max((item.version for item in prior_versions), default=0) + 1
        version = TemplateVersion.draft(
            version_id=f"TPL-{uuid4().hex}",
            template_key=template_key,
            version=next_version,
            page=page,
        )
        self._repository.add_version(version)
        return version

    def get(self, version_id: str) -> TemplateVersion:
        version = self._repository.get_version(version_id)
        if version is None:
            raise KeyError(f"Unknown template version: {version_id}")
        return version

    def add_field(self, version_id: str, definition: FieldDefinition) -> TemplateVersion:
        version = self.get(version_id)
        version.add_field(definition)
        self._repository.replace_version(version)
        return version

    def preflight(self, version_id: str) -> PreflightReport:
        version = self.get(version_id)
        issues = tuple(
            PreflightIssue(
                code="QR_SAFE_ZONE_OVERLAP",
                detail=f"Field {field.field_key} overlaps the template QR safe zone.",
            )
            for field in version.fields
            if _overlaps(field.region, _TEMPLATE_QR_SAFE_ZONE)
        )
        if issues:
            version.mark_preflight_failed()
        else:
            version.mark_ready_to_publish()
        self._repository.replace_version(version)
        return PreflightReport(issues)

    def publish(self, version_id: str) -> TemplateVersion:
        version = self.get(version_id)
        version.publish()
        self._repository.replace_version(version)
        return version

    def clone(self, version_id: str) -> TemplateVersion:
        source = self.get(version_id)
        if source.status is not TemplateStatus.PUBLISHED:
            raise ValueError("only published template versions can be cloned")
        clone = self.create_draft(source.template_key, source.page)
        clone.parent_version_id = source.version_id
        for definition in source.fields:
            clone.add_field(definition)
        self._repository.replace_version(clone)
        return clone


def _overlaps(left: Rect, right: Rect) -> bool:
    return (
        left.x < right.x + right.width
        and left.x + left.width > right.x
        and left.y < right.y + right.height
        and left.y + left.height > right.y
    )
