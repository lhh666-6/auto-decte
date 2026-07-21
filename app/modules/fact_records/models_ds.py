"""FactRecord domain models — the unified business-fact layer.

Every confirmed submission (electronic, paper-OCR, or admin-manual)
produces one or more FactRecords. A team-leader submission that covers
8 workers produces 8 FactRecords so that wages and statistics are
correctly attributed per worker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


# ── Enums ───────────────────────────────────────────────────────


class FactSourceType(StrEnum):
    ELECTRONIC = "ELECTRONIC"
    PAPER_OCR = "PAPER_OCR"
    ADMIN_MANUAL = "ADMIN_MANUAL"


class FactReviewStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CORRECTED = "CORRECTED"
    RETURNED = "RETURNED"
    VOIDED = "VOIDED"


class FactExportStatus(StrEnum):
    NOT_EXPORTED = "NOT_EXPORTED"
    EXPORTED = "EXPORTED"
    REEXPORT_REQUIRED = "REEXPORT_REQUIRED"


# ── Domain value objects ────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class FactAnomaly:
    """A structured anomaly flag on a fact record."""

    code: str
    severity: str  # BLOCKING | WARNING | INFO
    message: str
    field_key: str | None = None


@dataclass(frozen=True, slots=True)
class FactCorrection:
    """Immutable record of a correction applied to a fact record."""

    corrected_by: str
    corrected_at: datetime
    reason: str
    before: dict[str, Any]
    after: dict[str, Any]


# ── Aggregate root ──────────────────────────────────────────────


@dataclass(slots=True)
class FactRecord:
    """One row of standard business fact.

    A team-leader submission is split into one FactRecord per
    subject_employee_code so that every downstream report (wages,
    output statistics, process tracking) can group by worker.

    Mutable fields: review_status, export_status, anomalies,
    measurement_values, reviewed_by, reviewed_at.
    """

    fact_record_id: str
    source_type: FactSourceType
    source_submission_id: str | None = None
    source_form_id: str | None = None
    subject_employee_code: str = ""
    subject_employee_name: str = ""
    workshop: str = ""
    work_order_id: str = ""
    product_id: str = ""
    process_id: str = ""
    production_date: str = ""  # YYYY-MM-DD
    shift: str = ""
    blocks_completed: int | None = None
    pieces_per_block: int | None = None
    total_pieces: int | None = None
    measurement_values: dict[str, Any] = field(default_factory=dict)
    anomalies: list[dict[str, Any]] = field(default_factory=list)
    corrections: list[dict[str, Any]] = field(default_factory=list)
    review_status: FactReviewStatus = FactReviewStatus.PENDING
    reviewed_by: str = ""
    reviewed_at: datetime | None = None
    export_status: FactExportStatus = FactExportStatus.NOT_EXPORTED
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

    def confirm(self, reviewer: str) -> None:
        if self.review_status not in {FactReviewStatus.PENDING, FactReviewStatus.RETURNED}:
            raise ValueError(
                f"Cannot confirm a fact record with status {self.review_status.value}"
            )
        self.review_status = FactReviewStatus.CONFIRMED
        self.reviewed_by = reviewer
        self.reviewed_at = utc_now()
        self.updated_at = utc_now()

    def correct(
        self,
        reviewer: str,
        new_values: dict[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        """Apply a correction, returning the before/after snapshot."""
        before = {
            "subject_employee_code": self.subject_employee_code,
            "blocks_completed": self.blocks_completed,
            "pieces_per_block": self.pieces_per_block,
            "total_pieces": self.total_pieces,
            "measurement_values": dict(self.measurement_values),
            "production_date": self.production_date,
            "shift": self.shift,
        }
        for key, value in new_values.items():
            if hasattr(self, key):
                setattr(self, key, value)
        after = {
            "subject_employee_code": self.subject_employee_code,
            "blocks_completed": self.blocks_completed,
            "pieces_per_block": self.pieces_per_block,
            "total_pieces": self.total_pieces,
            "measurement_values": dict(self.measurement_values),
            "production_date": self.production_date,
            "shift": self.shift,
        }
        self.corrections.append({
            "corrected_by": reviewer,
            "corrected_at": utc_now().isoformat(),
            "reason": reason,
            "before": before,
            "after": after,
        })
        self.review_status = FactReviewStatus.CORRECTED
        self.export_status = FactExportStatus.REEXPORT_REQUIRED
        self.reviewed_by = reviewer
        self.reviewed_at = utc_now()
        self.updated_at = utc_now()
        return {"before": before, "after": after}

    def return_for_correction(self, reviewer: str, reason: str) -> None:
        self.review_status = FactReviewStatus.RETURNED
        self.reviewed_by = reviewer
        self.reviewed_at = utc_now()
        self.updated_at = utc_now()
        self.anomalies.append({
            "code": "RETURNED",
            "severity": "WARNING",
            "message": reason,
            "reviewer": reviewer,
            "timestamp": utc_now().isoformat(),
        })

    def void(self, reviewer: str, reason: str) -> None:
        self.review_status = FactReviewStatus.VOIDED
        self.reviewed_by = reviewer
        self.reviewed_at = utc_now()
        self.updated_at = utc_now()
        self.anomalies.append({
            "code": "VOIDED",
            "severity": "BLOCKING",
            "message": reason,
            "reviewer": reviewer,
            "timestamp": utc_now().isoformat(),
        })

    def mark_exported(self) -> None:
        self.export_status = FactExportStatus.EXPORTED
        self.updated_at = utc_now()

    def mark_reexport_required(self) -> None:
        self.export_status = FactExportStatus.REEXPORT_REQUIRED
        self.updated_at = utc_now()


# ── Domain errors ───────────────────────────────────────────────


class FactRecordError(Exception):
    """Base error for fact record module."""


class FactRecordNotFound(FactRecordError):
    def __init__(self, fact_record_id: str) -> None:
        super().__init__(f"Fact record not found: {fact_record_id}")
        self.fact_record_id = fact_record_id


class FactRecordAlreadyExists(FactRecordError):
    def __init__(self, source_submission_id: str, subject_employee_code: str) -> None:
        super().__init__(
            f"Fact record already exists for submission {source_submission_id} "
            f"and employee {subject_employee_code}"
        )
        self.source_submission_id = source_submission_id
        self.subject_employee_code = subject_employee_code
