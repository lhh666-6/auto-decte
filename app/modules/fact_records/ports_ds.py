"""FactRecord repository ports — abstract interfaces."""

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.modules.fact_records.models_ds import (
    FactExportStatus,
    FactRecord,
    FactReviewStatus,
    FactSourceType,
)


class FactRecordRepository(ABC):
    """Abstract repository for fact record persistence."""

    @abstractmethod
    def add(self, record: FactRecord) -> None:
        """Insert a new fact record."""

    @abstractmethod
    def get(self, fact_record_id: str) -> FactRecord | None:
        """Get a single fact record by ID."""

    @abstractmethod
    def list_by_source(
        self,
        source_submission_id: str,
    ) -> Sequence[FactRecord]:
        """List all fact records from a single submission."""

    @abstractmethod
    def list_by_employee(
        self,
        employee_code: str,
        *,
        production_date_from: str | None = None,
        production_date_to: str | None = None,
    ) -> Sequence[FactRecord]:
        """List fact records for an employee, optionally filtered by date range."""

    @abstractmethod
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
        """Search fact records with optional filters."""

    @abstractmethod
    def update(self, record: FactRecord) -> None:
        """Update an existing fact record."""

    @abstractmethod
    def count(
        self,
        *,
        review_status: FactReviewStatus | None = None,
        export_status: FactExportStatus | None = None,
    ) -> int:
        """Count fact records matching optional filters."""
