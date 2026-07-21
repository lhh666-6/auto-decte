"""Framework-independent business entities."""

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, cast


def utc_now() -> datetime:
    return datetime.now(UTC)


class ReviewStatus(StrEnum):
    IMPORTED = "IMPORTED"
    RECAPTURE_REQUIRED = "RECAPTURE_REQUIRED"
    CLASSIFIED = "CLASSIFIED"
    NEEDS_CLASSIFICATION = "NEEDS_CLASSIFICATION"
    RECOGNIZED = "RECOGNIZED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    AUTO_APPROVED = "AUTO_APPROVED"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    SUPERSEDED = "SUPERSEDED"
    VOIDED = "VOIDED"


class ExportStatus(StrEnum):
    NOT_EXPORTED = "NOT_EXPORTED"
    EXPORTED = "EXPORTED"
    REEXPORT_REQUIRED = "REEXPORT_REQUIRED"


class RecordStatus(StrEnum):
    DRAFT = "DRAFT"
    AUTO_APPROVED = "AUTO_APPROVED"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    SUPERSEDED = "SUPERSEDED"
    VOIDED = "VOIDED"


class AIStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    SUGGESTED = "SUGGESTED"
    UNAVAILABLE = "UNAVAILABLE"
    ADOPTED = "ADOPTED"
    REJECTED = "REJECTED"


class EvidenceType(StrEnum):
    ORIGINAL_IMAGE = "ORIGINAL_IMAGE"
    THUMBNAIL = "THUMBNAIL"
    AUDIO = "AUDIO"
    FIELD_CROP = "FIELD_CROP"
    CORRECTED_IMAGE = "CORRECTED_IMAGE"


class ValueSource(StrEnum):
    HUMAN_CONFIRMED = "HUMAN_CONFIRMED"
    AUTO_APPROVED = "AUTO_APPROVED"
    ELECTRONIC_SUBMITTED = "ELECTRONIC_SUBMITTED"


@dataclass(slots=True)
class Form:
    form_id: str
    template_id: str
    template_version: str
    coordinate_version: str = "1"
    review_status: ReviewStatus = ReviewStatus.IMPORTED
    export_status: ExportStatus = ExportStatus.NOT_EXPORTED
    current_record_version: int = 0
    priority: int = 0
    job_profile_key: str | None = None
    job_profile_version: str | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class FormField:
    field_id: str
    form_id: str
    field_name: str
    source_region: dict[str, int]
    current_value: Any = None
    current_value_source: ValueSource | None = None
    current_record_version: int = 0


@dataclass(slots=True)
class RecognitionAttempt:
    attempt_id: str
    field_id: str
    engine: str
    model_version: str
    candidate_value: Any
    confidence: float
    crop_file_id: str
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class EvidenceFile:
    file_id: str
    form_id: str
    type: EvidenceType
    uri: str
    sha256: str
    related_field_id: str | None = None
    immutable: bool = True
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class RecordVersion:
    record_id: str
    form_id: str
    version: int
    status: RecordStatus
    values: dict[str, Any]
    previous_version: int | None = None
    change_reason: str = ""
    confirmed_by: str | None = None
    created_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class AuditEvent:
    event_id: str
    form_id: str
    event_type: str
    actor_id: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    reason: str | None = None
    evidence_ids: tuple[str, ...] = ()
    timestamp: datetime = field(default_factory=utc_now)


def freeze_json(value: Any) -> Any:
    """Detach and recursively freeze one JSON-compatible value."""
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("JSON object keys must be strings")
            frozen[key] = freeze_json(item)
        return MappingProxyType(frozen)
    if isinstance(value, list | tuple):
        return tuple(freeze_json(item) for item in value)
    if value is None or isinstance(value, str | bool | int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("JSON numbers must be finite")
        return value
    raise TypeError(f"Unsupported JSON snapshot value: {type(value).__name__}")


def thaw_json(value: Any) -> Any:
    """Recursively copy a frozen JSON value to plain dictionaries and lists."""
    if isinstance(value, Mapping):
        return {key: thaw_json(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [thaw_json(item) for item in value]
    if value is None or isinstance(value, str | bool | int | float):
        return value
    raise TypeError(f"Unsupported frozen JSON value: {type(value).__name__}")


def stable_json_sha256(value: Any) -> str:
    """Hash a JSON-compatible value independently of dictionary key order."""
    serialized = json.dumps(
        thaw_json(value),
        allow_nan=False,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


@dataclass(frozen=True, slots=True)
class ExportBatch:
    export_batch_id: str
    export_type: str
    filters: Mapping[str, Any]
    included_records: tuple[tuple[str, int], ...]
    file_path: str
    file_sha256: str
    exported_by: str
    exported_at: datetime = field(default_factory=utc_now)
    supersedes_batch_id: str | None = None
    task_id: str | None = None
    template_snapshot: Mapping[str, Any] = field(default_factory=dict)
    mapping_snapshot: tuple[Mapping[str, Any], ...] = ()
    mapping_hash: str = ""
    download_name: str = "export.xlsx"

    def __post_init__(self) -> None:
        frozen_filters = freeze_json(self.filters)
        frozen_template = freeze_json(self.template_snapshot)
        frozen_mapping = freeze_json(self.mapping_snapshot)
        if not isinstance(frozen_filters, Mapping):
            raise TypeError("filters must be a JSON object")
        if not isinstance(frozen_template, Mapping):
            raise TypeError("template_snapshot must be a JSON object")
        if not isinstance(frozen_mapping, tuple) or any(
            not isinstance(item, Mapping) for item in frozen_mapping
        ):
            raise TypeError("mapping_snapshot must be a sequence of JSON objects")
        object.__setattr__(self, "filters", frozen_filters)
        object.__setattr__(self, "template_snapshot", frozen_template)
        object.__setattr__(
            self,
            "mapping_snapshot",
            cast(tuple[Mapping[str, Any], ...], frozen_mapping),
        )
        expected_hash = stable_json_sha256(self.mapping_snapshot)
        if self.mapping_hash and self.mapping_hash != expected_hash:
            raise ValueError("mapping_hash does not match mapping_snapshot")
        object.__setattr__(self, "mapping_hash", expected_hash)


@dataclass(slots=True)
class AIReviewRecord:
    review_id: str
    form_id: str
    status: AIStatus
    payload: dict[str, Any]
    created_at: datetime = field(default_factory=utc_now)
