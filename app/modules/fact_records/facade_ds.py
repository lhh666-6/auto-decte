"""FactRecord module facade — unified business-fact operations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from app.modules.fact_records.models_ds import (
    FactExportStatus,
    FactRecord,
    FactReviewStatus,
    FactSourceType,
)
from app.modules.fact_records.ports_ds import FactRecordRepository


class FactRecordFacade:
    """Boundary for fact record read/write operations.

    Depends on FactRecordRepository (abstract), receives concrete
    implementation via constructor injection from the container.
    """

    def __init__(self, repository: FactRecordRepository) -> None:
        self._repo = repository

    # ── Write ──────────────────────────────────────────────────

    def add(self, record: FactRecord) -> None:
        """Insert a new fact record (idempotent check optional)."""
        self._repo.add(record)

    def add_all(self, records: Sequence[FactRecord]) -> None:
        """Insert multiple fact records in a single batch."""
        for record in records:
            self._repo.add(record)

    def confirm(self, fact_record_id: str, reviewer: str) -> FactRecord:
        """Confirm a pending fact record."""
        record = self._repo.get(fact_record_id)
        if record is None:
            raise ValueError(f"Fact record not found: {fact_record_id}")
        record.confirm(reviewer)
        self._repo.update(record)
        return record

    def correct(
        self,
        fact_record_id: str,
        reviewer: str,
        new_values: dict[str, Any],
        reason: str,
    ) -> tuple[FactRecord, dict[str, Any]]:
        """Correct a fact record, returning the record + before/after snapshot."""
        record = self._repo.get(fact_record_id)
        if record is None:
            raise ValueError(f"Fact record not found: {fact_record_id}")
        snapshot = record.correct(reviewer, new_values, reason)
        self._repo.update(record)
        return record, snapshot

    def return_for_correction(
        self,
        fact_record_id: str,
        reviewer: str,
        reason: str,
    ) -> FactRecord:
        """Return a fact record for correction."""
        record = self._repo.get(fact_record_id)
        if record is None:
            raise ValueError(f"Fact record not found: {fact_record_id}")
        record.return_for_correction(reviewer, reason)
        self._repo.update(record)
        return record

    def void(self, fact_record_id: str, reviewer: str, reason: str) -> FactRecord:
        """Void a fact record."""
        record = self._repo.get(fact_record_id)
        if record is None:
            raise ValueError(f"Fact record not found: {fact_record_id}")
        record.void(reviewer, reason)
        self._repo.update(record)
        return record

    # ── Read ───────────────────────────────────────────────────

    def get(self, fact_record_id: str) -> FactRecord | None:
        return self._repo.get(fact_record_id)

    def list_by_source(
        self,
        source_submission_id: str,
    ) -> Sequence[FactRecord]:
        return self._repo.list_by_source(source_submission_id)

    def list_by_employee(
        self,
        employee_code: str,
        *,
        production_date_from: str | None = None,
        production_date_to: str | None = None,
    ) -> Sequence[FactRecord]:
        return self._repo.list_by_employee(
            employee_code,
            production_date_from=production_date_from,
            production_date_to=production_date_to,
        )

    def search(
        self,
        *,
        employee_code: str | None = None,
        workshop: str | None = None,
        work_order_id: str | None = None,
        product_id: str | None = None,
        process_id: str | None = None,
        production_date_from: str | None = None,
        production_date_to: str | None = None,
        review_status: FactReviewStatus | None = None,
        export_status: FactExportStatus | None = None,
        source_type: FactSourceType | None = None,
        limit: int = 500,
        offset: int = 0,
    ) -> Sequence[FactRecord]:
        return self._repo.search(
            employee_code=employee_code,
            workshop=workshop,
            work_order_id=work_order_id,
            product_id=product_id,
            process_id=process_id,
            production_date_from=production_date_from,
            production_date_to=production_date_to,
            review_status=review_status,
            export_status=export_status,
            source_type=source_type,
            limit=limit,
            offset=offset,
        )

    def count(
        self,
        *,
        review_status: FactReviewStatus | None = None,
        export_status: FactExportStatus | None = None,
    ) -> int:
        return self._repo.count(review_status=review_status, export_status=export_status)
