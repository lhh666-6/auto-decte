"""Template draft, preflight, publication and cloning use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from app.domain.templates_ds import FieldDefinition, PageSpec, Rect, TemplateStatus, TemplateVersion

_TEMPLATE_QR_SAFE_ZONE = Rect(0.78, 0.02, 0.16, 0.12)
_SHEET_CODE_SAFE_ZONE = Rect(0.62, 0.02, 0.14, 0.12)
_PRINT_EDGE = 0.025
_CORNER_MARKER = 0.07
_OTHER_PROTECTED_ZONES = (
    (
        "SHEET_SAFE_ZONE_OVERLAP",
        "sheet-instance QR safe zone",
        _SHEET_CODE_SAFE_ZONE,
    ),
    ("CORNER_MARKER_OVERLAP", "top-left ArUco marker", Rect(0, 0, _CORNER_MARKER, _CORNER_MARKER)),
    (
        "CORNER_MARKER_OVERLAP",
        "top-right ArUco marker",
        Rect(1 - _CORNER_MARKER, 0, _CORNER_MARKER, _CORNER_MARKER),
    ),
    (
        "CORNER_MARKER_OVERLAP",
        "bottom-left ArUco marker",
        Rect(0, 1 - _CORNER_MARKER, _CORNER_MARKER, _CORNER_MARKER),
    ),
    (
        "CORNER_MARKER_OVERLAP",
        "bottom-right ArUco marker",
        Rect(1 - _CORNER_MARKER, 1 - _CORNER_MARKER, _CORNER_MARKER, _CORNER_MARKER),
    ),
    ("PRINT_EDGE_OVERLAP", "top print edge", Rect(0, 0, 1, _PRINT_EDGE)),
    ("PRINT_EDGE_OVERLAP", "bottom print edge", Rect(0, 1 - _PRINT_EDGE, 1, _PRINT_EDGE)),
    ("PRINT_EDGE_OVERLAP", "left print edge", Rect(0, 0, _PRINT_EDGE, 1)),
    ("PRINT_EDGE_OVERLAP", "right print edge", Rect(1 - _PRINT_EDGE, 0, _PRINT_EDGE, 1)),
)


class TemplateVersionRepository(Protocol):
    def add_version(self, version: TemplateVersion) -> None: ...

    def get_version(self, version_id: str) -> TemplateVersion | None: ...

    def replace_version(self, version: TemplateVersion) -> None: ...

    def list_versions(self, template_key: str) -> list[TemplateVersion]: ...

    def list_template_keys(self) -> list[str]: ...


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

    def list_templates(self) -> list[TemplateVersion]:
        versions = [
            version
            for template_key in self._repository.list_template_keys()
            for version in self._repository.list_versions(template_key)
        ]
        return sorted(
            versions,
            key=lambda version: (version.template_key, version.version, version.version_id),
        )

    def add_field(self, version_id: str, definition: FieldDefinition) -> TemplateVersion:
        version = self.get(version_id)
        version.add_field(definition)
        self._repository.replace_version(version)
        return version

    def replace_field(
        self, version_id: str, field_key: str, definition: FieldDefinition
    ) -> TemplateVersion:
        version = self.get(version_id)
        version.replace_field(field_key, definition)
        self._repository.replace_version(version)
        return version

    def remove_field(self, version_id: str, field_key: str) -> TemplateVersion:
        version = self.get(version_id)
        version.remove_field(field_key)
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
        ) + tuple(
            issue
            for field in version.fields
            for issue in _protected_zone_issues(field)
        ) + tuple(
            PreflightIssue(
                code="RECOGNITION_ENGINE_MISMATCH",
                detail=(
                    f"Field {field.field_key} uses {field.recognition_engine} with "
                    f"{field.input_type}/{field.data_type}."
                ),
            )
            for field in version.fields
            if not _recognition_configuration_is_valid(field)
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


def _recognition_configuration_is_valid(field: FieldDefinition) -> bool:
    if field.recognition_engine == "manual":
        return True
    if field.recognition_engine == "digit_template":
        return field.input_type == "digit_boxes" and field.data_type in {"integer", "decimal"}
    if field.recognition_engine == "omr":
        return field.input_type == "checkbox" and field.data_type == "boolean"
    return False


def _protected_zone_issues(field: FieldDefinition) -> tuple[PreflightIssue, ...]:
    if _overlaps(field.region, _TEMPLATE_QR_SAFE_ZONE):
        return ()
    for code, label, zone in _OTHER_PROTECTED_ZONES:
        if _overlaps(field.region, zone):
            return (
                PreflightIssue(
                    code=code,
                    detail=f"Field {field.field_key} overlaps the {label}.",
                ),
            )
    return ()
