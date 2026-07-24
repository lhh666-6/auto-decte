"""Electronic form domain models — definitions, drafts, submission receipts.

Independent of the paper-scanning pipeline. Represents mobile/PWA
electronic form filling that feeds into the same review workflow.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


# ── Enums ───────────────────────────────────────────────────────

class DefinitionStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RETIRED = "RETIRED"


class DraftSyncStatus(StrEnum):
    LOCAL_ONLY = "LOCAL_ONLY"
    SYNCED = "SYNCED"
    CONFLICT = "CONFLICT"


class ReceiptOperation(StrEnum):
    CREATE_ELECTRONIC_FORM = "CREATE_ELECTRONIC_FORM"


class SubmissionReceiptStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    CONFIRMED = "CONFIRMED"
    RETURNED = "RETURNED"
    VOIDED = "VOIDED"


# ── Domain value objects ────────────────────────────────────────

@dataclass(slots=True, frozen=True)
class PresentationField:
    """Mobile display config for a single field. Coordinates are NOT copied
    from paper templates — this only controls mobile rendering order, group,
    strategy, and conditional rules."""

    field_key: str
    display_order: int
    group: str | None = None
    strategy: str = "DEFAULT_EDITABLE"  # AUTO_HIDDEN, AUTO_READ_ONLY, etc.
    condition_rule: dict[str, Any] | None = None  # {"depends_on": "…", "show_when": "…"}


@dataclass(slots=True, frozen=True)
class PresentationConfig:
    """Mobile presentation config stored in a definition version."""
    fields: list[PresentationField]
    groups: list[str] | None = None


# ── Aggregate roots ─────────────────────────────────────────────

@dataclass(slots=True)
class ElectronicFormDefinitionVersion:
    """Immutable once published. Binds a mobile form type to a published
    template version and optional job-profile version."""

    definition_version_id: str
    form_type: str
    version: int
    status: DefinitionStatus = DefinitionStatus.DRAFT
    template_version_id: str | None = None
    job_profile_version_id: str | None = None
    presentation_config: PresentationConfig | None = None
    display_name: str = ""
    created_by: str = ""
    created_at: datetime = field(default_factory=utc_now)
    published_at: datetime | None = None

    def publish(self) -> None:
        if self.status != DefinitionStatus.DRAFT:
            raise ValueError("Only DRAFT definitions can be published.")
        # OCR retired: template_version_id is no longer required.
        # Electronic forms can be published standalone.
        self.status = DefinitionStatus.PUBLISHED
        self.published_at = utc_now()

    def retire(self) -> None:
        self.status = DefinitionStatus.RETIRED


@dataclass(slots=True)
class ElectronicDraft:
    """A server-side synced draft. Updated with optimistic revision checks."""

    draft_id: str
    owner_actor_id: str
    subject_employee_code: str
    device_id: str
    definition_version_id: str
    values: dict[str, Any] = field(default_factory=dict)
    revision: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def update_values(
        self, new_values: dict[str, Any], expected_revision: int,
    ) -> None:
        if expected_revision != self.revision:
            raise DraftRevisionConflict(self.draft_id, expected_revision, self.revision)
        self.values = {**new_values}
        self.revision += 1
        self.updated_at = utc_now()


@dataclass(slots=True)
class ElectronicSubmissionReceipt:
    """Immutable proof that an electronic submission was accepted.
    Uniqueness enforced on (actor_id, device_id, operation, client_submission_id)."""

    receipt_id: str
    actor_id: str
    subject_employee_code: str
    device_id: str
    operation: ReceiptOperation = ReceiptOperation.CREATE_ELECTRONIC_FORM
    client_submission_id: str = ""
    payload_hash: str = ""
    form_id: str | None = None
    record_version: int | None = None
    status: SubmissionReceiptStatus = SubmissionReceiptStatus.ACCEPTED
    submitted_at: datetime = field(default_factory=utc_now)


# ── Domain errors ──────────────────────────────────────────────

class ElectronicFormsError(Exception):
    """Base error for electronic forms module."""


class DraftRevisionConflict(ElectronicFormsError):
    def __init__(self, draft_id: str, expected: int, actual: int) -> None:
        super().__init__(
            f"Draft {draft_id} revision conflict: "
            f"expected {expected}, actual {actual}",
        )
        self.draft_id = draft_id
        self.expected = expected
        self.actual = actual


class DefinitionNotPublished(ElectronicFormsError):
    def __init__(self, form_type: str) -> None:
        super().__init__(f"Definition for {form_type} is not published.")
        self.form_type = form_type


class IdempotencyConflict(ElectronicFormsError):
    def __init__(self, client_submission_id: str) -> None:
        super().__init__(
            f"Idempotency conflict: {client_submission_id} "
            "already submitted with different payload.",
        )
        self.client_submission_id = client_submission_id


class SchemaVersionConflict(ElectronicFormsError):
    def __init__(self, form_type: str) -> None:
        super().__init__(
            f"Schema version conflict for {form_type}. "
            "Reload the form definition and retry.",
        )
        self.form_type = form_type
