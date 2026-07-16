"""Immutable reporting values used to preview template-driven exports."""

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True, slots=True)
class ExportMapping:
    """A stable template field mapping independent of its display label."""

    template_id: str
    template_version: str
    field_key: str
    workbook: str
    worksheet: str
    business_column: str


class ExportExclusionReason(StrEnum):
    """Machine-readable reason a candidate form cannot be exported."""

    NOT_CONFIRMED = "NOT_CONFIRMED"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    NO_VALID_MAPPING = "NO_VALID_MAPPING"
    FINAL_VALIDATION_FAILED = "FINAL_VALIDATION_FAILED"


class ExportReasonScope(StrEnum):
    """The record level addressed by an export exclusion reason."""

    FORM = "FORM"
    FIELD = "FIELD"


class ExportTaskPublicError(StrEnum):
    """Stable task errors safe to expose through external APIs."""

    FAILED = "EXPORT_FAILED: Export could not be completed."
    STORAGE_ACCESS_FAILED = (
        "EXPORT_STORAGE_ACCESS_FAILED: Export storage is unavailable."
    )
    INTEGRITY_FAILED = (
        "EXPORT_INTEGRITY_FAILED: Export file failed integrity verification."
    )
    VALIDATION_FAILED = (
        "EXPORT_VALIDATION_FAILED: Export request failed validation."
    )
    COMPLETION_FAILED = (
        "EXPORT_COMPLETION_FAILED: Export source data changed before completion."
    )
    RECOVERY_FAILED = (
        "EXPORT_RECOVERY_FAILED: Export recovery could not be completed."
    )


@dataclass(frozen=True, slots=True)
class ExportValidationReason:
    """A safe, structured explanation for an excluded form."""

    scope: ExportReasonScope
    code: str
    message: str
    field_key: str | None = None
    required: bool | None = None
    allowed_values: tuple[str, ...] | None = None
    minimum_value: float | None = None
    maximum_value: float | None = None


@dataclass(frozen=True, slots=True)
class ExportPreviewItem:
    """One versioned candidate and its optional exclusion reason."""

    form_id: str
    record_version: int
    reason: ExportExclusionReason | None = None
    reasons: tuple[ExportValidationReason, ...] = ()


@dataclass(frozen=True, slots=True)
class ExportPreview:
    """Read-only decision result for a filtered export request."""

    included: tuple[ExportPreviewItem, ...]
    excluded: tuple[ExportPreviewItem, ...]
    mapping_snapshot: tuple[ExportMapping, ...]
