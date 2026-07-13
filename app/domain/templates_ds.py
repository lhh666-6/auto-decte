"""Framework-independent template definitions for paper forms."""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field
from enum import StrEnum

_TEMPLATE_KEY = re.compile(r"^[A-Z][A-Z0-9_]*$")
_BATCH_KEY = re.compile(r"^[A-Z0-9][A-Z0-9_-]*$")


class TemplateStatus(StrEnum):
    """Lifecycle of a template version."""

    DRAFT = "DRAFT"
    PREFLIGHT_FAILED = "PREFLIGHT_FAILED"
    READY_TO_PUBLISH = "READY_TO_PUBLISH"
    PUBLISHED = "PUBLISHED"
    DEPRECATED = "DEPRECATED"
    RETIRED = "RETIRED"


@dataclass(frozen=True, slots=True)
class PageSpec:
    """Canonical post-correction paper canvas."""

    size: str
    orientation: str
    width_mm: int
    height_mm: int
    canonical_dpi: int
    canonical_width_px: int
    canonical_height_px: int

    @classmethod
    def a4_portrait(cls) -> PageSpec:
        return cls("A4", "portrait", 210, 297, 300, 2480, 3508)

    @classmethod
    def a5_portrait(cls) -> PageSpec:
        return cls("A5", "portrait", 148, 210, 300, 1748, 2480)


@dataclass(frozen=True, slots=True)
class Rect:
    """Normalized rectangular region on a canonical canvas."""

    x: float
    y: float
    width: float
    height: float

    def is_inside(self) -> bool:
        return (
            0 <= self.x < 1
            and 0 <= self.y < 1
            and self.width > 0
            and self.height > 0
            and self.x + self.width <= 1
            and self.y + self.height <= 1
        )


@dataclass(frozen=True, slots=True)
class FieldDefinition:
    """A stable, rectangular field declared by a template version."""

    field_key: str
    display_name: str
    data_type: str
    input_type: str
    region: Rect
    page: PageSpec

    def __post_init__(self) -> None:
        if not self.field_key or not re.fullmatch(r"[a-z][a-z0-9_]*", self.field_key):
            raise ValueError("field_key must be lower snake case")
        if not self.display_name.strip():
            raise ValueError("display_name is required")
        if not self.region.is_inside():
            raise ValueError("field region must be inside canonical canvas")


@dataclass(slots=True)
class TemplateVersion:
    """Editable draft or immutable published template version."""

    version_id: str
    template_key: str
    version: int
    page: PageSpec
    status: TemplateStatus = TemplateStatus.DRAFT
    fields: list[FieldDefinition] = field(default_factory=list)
    parent_version_id: str | None = None

    @classmethod
    def draft(
        cls,
        version_id: str,
        template_key: str,
        version: int,
        page: PageSpec,
        parent_version_id: str | None = None,
    ) -> TemplateVersion:
        _validate_template_key(template_key)
        if version < 1:
            raise ValueError("version must be a positive integer")
        return cls(version_id, template_key, version, page, parent_version_id=parent_version_id)

    def add_field(self, definition: FieldDefinition) -> None:
        self._require_draft()
        if definition.page != self.page:
            raise ValueError("field page must match template page")
        if definition.field_key in {item.field_key for item in self.fields}:
            raise ValueError("field_key must be unique within a template version")
        self.fields.append(definition)

    def publish(self) -> None:
        self._require_draft()
        self.status = TemplateStatus.PUBLISHED

    def _require_draft(self) -> None:
        if self.status is not TemplateStatus.DRAFT:
            raise ValueError("published template versions cannot be mutated")


@dataclass(frozen=True, slots=True)
class TemplateArtifact:
    """A generated printable artifact whose storage URI stays server-side."""

    artifact_id: str
    version_id: str
    kind: str
    download_name: str
    internal_uri: str
    sha256: str

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.version_id:
            raise ValueError("artifact_id and version_id are required")
        if not re.fullmatch(r"[A-Za-z0-9._-]+", self.download_name):
            raise ValueError("download_name must be a safe file name")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("sha256 must be a lowercase hexadecimal digest")


def build_template_payload(template_key: str, version: int) -> str:
    """Build the small QR payload that binds a paper to its template version."""
    _validate_template_key(template_key)
    if version < 1:
        raise ValueError("version must be a positive integer")
    checksum = _checksum(f"{template_key}|{version}")
    return f"IFD|{template_key}|{version}|{checksum}"


def build_sheet_payload(print_batch: str, sequence: int) -> str:
    """Build the optional non-business paper-instance QR payload."""
    if not _BATCH_KEY.fullmatch(print_batch):
        raise ValueError("print_batch must use uppercase ASCII letters, digits, _ or -")
    if sequence < 1 or sequence > 999999:
        raise ValueError("sequence must be between 1 and 999999")
    padded = f"{sequence:06d}"
    checksum = _checksum(f"{print_batch}|{padded}")
    return f"SHEET|{print_batch}|{padded}|{checksum}"


def _validate_template_key(template_key: str) -> None:
    if not _TEMPLATE_KEY.fullmatch(template_key):
        raise ValueError("template_key must use uppercase ASCII letters, digits and underscores")


def _checksum(value: str) -> str:
    return f"{zlib.crc32(value.encode('ascii')) & 0xFFFF:04X}"
