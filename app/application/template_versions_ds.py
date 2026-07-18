"""Template draft, preflight, publication and cloning use cases."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from app.domain.templates_ds import (
    ElementKind,
    FieldDefinition,
    PageSpec,
    PrintImposition,
    Rect,
    StaticElement,
    TemplateStatus,
    TemplateVersion,
)

_OUTER_MARGIN_MM = 5.0
_QR_SAFE_ZONE_MM = 29.0
_QR_GAP_MM = 5.0
_CORNER_MARKER_MM = 12.0
_FIELD_MINIMUMS_MM = {
    "employee_id_boxes": (6.0, 8.0),
    "digit_boxes": (7.0, 8.0),
    "checkbox": (4.0, 4.0),
    "handwriting_line": (0.0, 8.0),
    "text_box": (0.0, 8.0),
}


class TemplateVersionRepository(Protocol):
    def add_version(self, version: TemplateVersion) -> None: ...

    def get_version(self, version_id: str) -> TemplateVersion | None: ...

    def replace_version(self, version: TemplateVersion) -> None: ...

    def list_versions(self, template_key: str) -> list[TemplateVersion]: ...

    def list_template_keys(self) -> list[str]: ...

    def get_template_metadata(self, template_key: str) -> tuple[str, str] | None: ...

    def update_template_metadata(
        self, template_key: str, display_name: str, description: str
    ) -> None: ...

    def delete_version(self, version_id: str) -> None: ...


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

    def create_draft(
        self,
        template_key: str,
        page: PageSpec,
        display_name: str | None = None,
        description: str = "",
    ) -> TemplateVersion:
        prior_versions = self._repository.list_versions(template_key)
        next_version = max((item.version for item in prior_versions), default=0) + 1
        version = TemplateVersion.draft(
            version_id=f"TPL-{uuid4().hex}",
            template_key=template_key,
            version=next_version,
            page=page,
        )
        self._repository.add_version(version)
        if display_name is not None:
            self.update_metadata(template_key, display_name, description)
        return version

    def get_metadata(self, template_key: str) -> tuple[str, str]:
        metadata = self._repository.get_template_metadata(template_key)
        if metadata is None:
            raise KeyError(f"Unknown template: {template_key}")
        return metadata

    def update_metadata(
        self, template_key: str, display_name: str, description: str
    ) -> tuple[str, str]:
        cleaned_name = display_name.strip()
        cleaned_description = description.strip()
        if not cleaned_name:
            raise ValueError("template display name is required")
        if len(cleaned_name) > 100:
            raise ValueError("template display name must not exceed 100 characters")
        if len(cleaned_description) > 500:
            raise ValueError("template description must not exceed 500 characters")
        self._repository.update_template_metadata(
            template_key, cleaned_name, cleaned_description
        )
        return cleaned_name, cleaned_description

    def discard_draft(self, version_id: str) -> None:
        version = self.get(version_id)
        if version.status not in {
            TemplateStatus.DRAFT,
            TemplateStatus.PREFLIGHT_FAILED,
            TemplateStatus.READY_TO_PUBLISH,
        }:
            raise ValueError("only editable template drafts can be discarded")
        self._repository.delete_version(version_id)

    def retire_template(self, template_key: str) -> None:
        versions = self._repository.list_versions(template_key)
        if not versions:
            raise KeyError(f"Unknown template: {template_key}")
        editable = {
            TemplateStatus.DRAFT,
            TemplateStatus.PREFLIGHT_FAILED,
            TemplateStatus.READY_TO_PUBLISH,
        }
        if any(version.status in editable for version in versions):
            raise ValueError("discard active drafts before retiring the template")
        candidates = [
            version
            for version in versions
            if version.status in {TemplateStatus.PUBLISHED, TemplateStatus.DEPRECATED}
        ]
        if not candidates:
            raise ValueError("template has no active published versions to retire")
        for version in candidates:
            version.retire()
            self._repository.replace_version(version)

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

    def add_static_element(self, version_id: str, element: StaticElement) -> TemplateVersion:
        version = self.get(version_id)
        version.add_static_element(element)
        self._repository.replace_version(version)
        return version

    def set_print_imposition(
        self, version_id: str, imposition: PrintImposition | None
    ) -> TemplateVersion:
        version = self.get(version_id)
        version.set_print_imposition(imposition)
        self._repository.replace_version(version)
        return version

    def preflight(self, version_id: str) -> PreflightReport:
        version = self.get(version_id)
        issues = tuple(
            issue
            for field in version.fields
            for issue in _protected_zone_issues(
                field.region,
                version.page,
                item_label=f"Field {field.field_key}",
            )
        ) + tuple(
            issue
            for field in version.fields
            for issue in _physical_field_issues(field)
        ) + tuple(
            issue
            for element in version.static_elements
            for issue in _protected_zone_issues(
                element.region,
                version.page,
                item_label=f"Static element {element.element_id}",
            )
        ) + tuple(
            issue
            for element in version.static_elements
            for issue in _physical_static_element_issues(element, version.page)
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
        if version.print_imposition is not None and not version.print_imposition.fits(version.page):
            issues += (
                PreflightIssue(
                    code="IMPOSITION_DOES_NOT_FIT",
                    detail="The template page does not fit in each configured imposition slot.",
                ),
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
        for element in source.static_elements:
            clone.add_static_element(element)
        clone.set_print_imposition(source.print_imposition)
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


def _protected_zone_issues(
    region: Rect,
    page: PageSpec,
    *,
    item_label: str,
) -> tuple[PreflightIssue, ...]:
    return tuple(
        PreflightIssue(code=code, detail=f"{item_label} overlaps the {label}.")
        for code, label, zone in _protected_zones(page)
        if _overlaps(region, zone)
    )


def _protected_zones(page: PageSpec) -> tuple[tuple[str, str, Rect], ...]:
    edge_x = _OUTER_MARGIN_MM / page.width_mm
    edge_y = _OUTER_MARGIN_MM / page.height_mm
    marker_width = _CORNER_MARKER_MM / page.width_mm
    marker_height = _CORNER_MARKER_MM / page.height_mm
    qr_width = _QR_SAFE_ZONE_MM / page.width_mm
    qr_height = _QR_SAFE_ZONE_MM / page.height_mm
    template_qr_x = 1 - edge_x - qr_width
    sheet_qr_x = template_qr_x - _QR_GAP_MM / page.width_mm - qr_width
    return (
        (
            "QR_SAFE_ZONE_OVERLAP",
            "template QR safe zone",
            Rect(template_qr_x, edge_y, qr_width, qr_height),
        ),
        (
            "SHEET_SAFE_ZONE_OVERLAP",
            "sheet-instance QR safe zone",
            Rect(sheet_qr_x, edge_y, qr_width, qr_height),
        ),
        (
            "CORNER_MARKER_OVERLAP",
            "top-left ArUco marker",
            Rect(0, 0, marker_width, marker_height),
        ),
        (
            "CORNER_MARKER_OVERLAP",
            "top-right ArUco marker",
            Rect(1 - marker_width, 0, marker_width, marker_height),
        ),
        (
            "CORNER_MARKER_OVERLAP",
            "bottom-left ArUco marker",
            Rect(0, 1 - marker_height, marker_width, marker_height),
        ),
        (
            "CORNER_MARKER_OVERLAP",
            "bottom-right ArUco marker",
            Rect(1 - marker_width, 1 - marker_height, marker_width, marker_height),
        ),
        ("PRINT_EDGE_OVERLAP", "top print edge", Rect(0, 0, 1, edge_y)),
        ("PRINT_EDGE_OVERLAP", "bottom print edge", Rect(0, 1 - edge_y, 1, edge_y)),
        ("PRINT_EDGE_OVERLAP", "left print edge", Rect(0, 0, edge_x, 1)),
        ("PRINT_EDGE_OVERLAP", "right print edge", Rect(1 - edge_x, 0, edge_x, 1)),
    )


def _physical_field_issues(field: FieldDefinition) -> tuple[PreflightIssue, ...]:
    minimum = _FIELD_MINIMUMS_MM.get(field.input_type)
    if minimum is None:
        return ()
    width_mm = field.region.width * field.page.width_mm
    height_mm = field.region.height * field.page.height_mm
    if width_mm + 1e-9 >= minimum[0] and height_mm + 1e-9 >= minimum[1]:
        return ()
    return (
        PreflightIssue(
            code="PHYSICAL_MINIMUM_SIZE",
            detail=(
                f"Field {field.field_key} is {width_mm:.1f} x {height_mm:.1f} mm; "
                f"{field.input_type} requires at least {minimum[0]:.1f} x {minimum[1]:.1f} mm."
            ),
        ),
    )


def _physical_static_element_issues(
    element: StaticElement, page: PageSpec
) -> tuple[PreflightIssue, ...]:
    if element.kind is not ElementKind.CHECKBOX:
        return ()
    width_mm = element.region.width * page.width_mm
    height_mm = element.region.height * page.height_mm
    if width_mm + 1e-9 >= 4 and height_mm + 1e-9 >= 4:
        return ()
    return (
        PreflightIssue(
            code="PHYSICAL_MINIMUM_SIZE",
            detail=(
                f"Static element {element.element_id} is {width_mm:.1f} x {height_mm:.1f} mm; "
                "checkboxes require at least 4.0 x 4.0 mm."
            ),
        ),
    )
