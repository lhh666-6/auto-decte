"""SQLAlchemy repository for fact records."""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.adapters.database.models import FactRecordRow
from app.modules.fact_records.models_ds import (
    FactExportStatus,
    FactRecord,
    FactRecordNotFound,
    FactReviewStatus,
    FactSourceType,
)
from app.modules.fact_records.ports_ds import FactRecordRepository


class SqlAlchemyFactRecordRepository(FactRecordRepository):
    """SQLAlchemy implementation of FactRecordRepository."""

    def __init__(self, engine: Engine, session: Session | None = None) -> None:
        self._engine = engine
        self._session = session

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        if self._session is not None:
            yield self._session
            return
        with Session(self._engine) as session, session.begin():
            yield session

    @contextmanager
    def _read_session(self) -> Iterator[Session]:
        if self._session is not None:
            yield self._session
            return
        with Session(self._engine) as session:
            yield session

    def add(self, record: FactRecord) -> None:
        with self._transaction() as session:
            row = _fact_row(record)
            session.add(row)

    def get(self, fact_record_id: str) -> FactRecord | None:
        with self._read_session() as session:
            row = session.get(FactRecordRow, fact_record_id)
            return _fact_record(row) if row is not None else None

    def list_by_source(
        self,
        source_submission_id: str,
    ) -> Sequence[FactRecord]:
        statement = (
            select(FactRecordRow)
            .where(FactRecordRow.source_submission_id == source_submission_id)
            .order_by(FactRecordRow.subject_employee_code)
        )
        with self._read_session() as session:
            return tuple(_fact_record(row) for row in session.scalars(statement))

    def list_by_employee(
        self,
        employee_code: str,
        *,
        production_date_from: str | None = None,
        production_date_to: str | None = None,
    ) -> Sequence[FactRecord]:
        statement = select(FactRecordRow).where(
            FactRecordRow.subject_employee_code == employee_code,
        )
        if production_date_from:
            statement = statement.where(
                FactRecordRow.production_date >= production_date_from,
            )
        if production_date_to:
            statement = statement.where(
                FactRecordRow.production_date <= production_date_to,
            )
        statement = statement.order_by(
            FactRecordRow.production_date.desc(),
            FactRecordRow.created_at.desc(),
        )
        with self._read_session() as session:
            return tuple(_fact_record(row) for row in session.scalars(statement))

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
        statement = select(FactRecordRow)
        if employee_code:
            statement = statement.where(
                FactRecordRow.subject_employee_code == employee_code,
            )
        if workshop:
            statement = statement.where(FactRecordRow.workshop == workshop)
        if work_order_id:
            statement = statement.where(FactRecordRow.work_order_id == work_order_id)
        if product_id:
            statement = statement.where(FactRecordRow.product_id == product_id)
        if process_id:
            statement = statement.where(FactRecordRow.process_id == process_id)
        if production_date_from:
            statement = statement.where(
                FactRecordRow.production_date >= production_date_from,
            )
        if production_date_to:
            statement = statement.where(
                FactRecordRow.production_date <= production_date_to,
            )
        if review_status:
            statement = statement.where(
                FactRecordRow.review_status == review_status.value,
            )
        if export_status:
            statement = statement.where(
                FactRecordRow.export_status == export_status.value,
            )
        if source_type:
            statement = statement.where(
                FactRecordRow.source_type == source_type.value,
            )
        statement = statement.order_by(
            FactRecordRow.production_date.desc(),
            FactRecordRow.created_at.desc(),
        ).offset(offset).limit(limit)
        with self._read_session() as session:
            return tuple(_fact_record(row) for row in session.scalars(statement))

    def update(self, record: FactRecord) -> None:
        with self._transaction() as session:
            result = session.execute(
                update(FactRecordRow)
                .where(FactRecordRow.fact_record_id == record.fact_record_id)
                .values(
                    subject_employee_code=record.subject_employee_code,
                    subject_employee_name=record.subject_employee_name,
                    workshop=record.workshop,
                    work_order_id=record.work_order_id,
                    product_id=record.product_id,
                    process_id=record.process_id,
                    production_date=record.production_date,
                    shift=record.shift,
                    blocks_completed=record.blocks_completed,
                    pieces_per_block=record.pieces_per_block,
                    total_pieces=record.total_pieces,
                    measurement_values=record.measurement_values,
                    anomalies=record.anomalies,
                    corrections=record.corrections,
                    review_status=record.review_status.value,
                    reviewed_by=record.reviewed_by,
                    reviewed_at=record.reviewed_at,
                    export_status=record.export_status.value,
                    updated_at=record.updated_at,
                )
            )
            if getattr(result, "rowcount", None) != 1:
                raise FactRecordNotFound(record.fact_record_id)

    def count(
        self,
        *,
        review_status: FactReviewStatus | None = None,
        export_status: FactExportStatus | None = None,
    ) -> int:
        from sqlalchemy import func

        statement = select(func.count()).select_from(FactRecordRow)
        if review_status:
            statement = statement.where(
                FactRecordRow.review_status == review_status.value,
            )
        if export_status:
            statement = statement.where(
                FactRecordRow.export_status == export_status.value,
            )
        with self._read_session() as session:
            return session.scalar(statement) or 0


# ── Row ↔ Domain mappers ────────────────────────────────────────


def _fact_record(row: FactRecordRow) -> FactRecord:
    return FactRecord(
        fact_record_id=row.fact_record_id,
        source_type=FactSourceType(row.source_type),
        source_submission_id=row.source_submission_id,
        source_form_id=row.source_form_id,
        subject_employee_code=row.subject_employee_code,
        subject_employee_name=row.subject_employee_name,
        workshop=row.workshop,
        work_order_id=row.work_order_id,
        product_id=row.product_id,
        process_id=row.process_id,
        production_date=row.production_date,
        shift=row.shift,
        blocks_completed=row.blocks_completed,
        pieces_per_block=row.pieces_per_block,
        total_pieces=row.total_pieces,
        measurement_values=_copy_json(row.measurement_values),
        anomalies=_copy_json_list(row.anomalies),
        corrections=_copy_json_list(row.corrections),
        review_status=FactReviewStatus(row.review_status),
        reviewed_by=row.reviewed_by,
        reviewed_at=row.reviewed_at,
        export_status=FactExportStatus(row.export_status),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _fact_row(record: FactRecord) -> FactRecordRow:
    return FactRecordRow(
        fact_record_id=record.fact_record_id,
        source_type=record.source_type.value,
        source_submission_id=record.source_submission_id,
        source_form_id=record.source_form_id,
        subject_employee_code=record.subject_employee_code,
        subject_employee_name=record.subject_employee_name,
        workshop=record.workshop,
        work_order_id=record.work_order_id,
        product_id=record.product_id,
        process_id=record.process_id,
        production_date=record.production_date,
        shift=record.shift,
        blocks_completed=record.blocks_completed,
        pieces_per_block=record.pieces_per_block,
        total_pieces=record.total_pieces,
        measurement_values=record.measurement_values,
        anomalies=record.anomalies,
        corrections=record.corrections,
        review_status=record.review_status.value,
        reviewed_by=record.reviewed_by,
        reviewed_at=record.reviewed_at,
        export_status=record.export_status.value,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _copy_json(value: Any) -> Any:
    if isinstance(value, dict):
        return dict(value)
    return value


def _copy_json_list(value: Any) -> Any:
    if isinstance(value, list):
        return list(value)
    return value
