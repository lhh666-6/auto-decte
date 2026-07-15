"""SQLAlchemy repository for versioned master data."""

from __future__ import annotations

from sqlalchemy import Engine, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.database.models import MasterDataAuditRow, MasterDataRecordRow
from app.modules.master_data.models_ds import (
    MasterDataAlreadyExists,
    MasterDataAudit,
    MasterDataCatalog,
    MasterDataNotFound,
    MasterDataRecord,
    MasterDataRevisionConflict,
)


class SqlAlchemyMasterDataRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, catalog: MasterDataCatalog, code: str) -> MasterDataRecord | None:
        with Session(self._engine) as session:
            row = session.get(MasterDataRecordRow, (catalog.value, code))
            return _record(row) if row is not None else None

    def list_records(
        self,
        catalog: MasterDataCatalog,
        *,
        include_inactive: bool = False,
        query: str | None = None,
    ) -> list[MasterDataRecord]:
        statement = select(MasterDataRecordRow).where(MasterDataRecordRow.catalog == catalog.value)
        if not include_inactive:
            statement = statement.where(MasterDataRecordRow.active.is_(True))
        if query:
            pattern = f"%{query}%"
            statement = statement.where(
                or_(
                    MasterDataRecordRow.code.ilike(pattern),
                    MasterDataRecordRow.display_name.ilike(pattern),
                )
            )
        statement = statement.order_by(MasterDataRecordRow.display_name, MasterDataRecordRow.code)
        with Session(self._engine) as session:
            return [_record(row) for row in session.scalars(statement)]

    def create(self, record: MasterDataRecord, audit: MasterDataAudit) -> None:
        try:
            with Session(self._engine) as session, session.begin():
                session.add(_record_row(record))
                session.add(_audit_row(audit))
        except IntegrityError as error:
            raise MasterDataAlreadyExists(record.code) from error

    def update(
        self,
        record: MasterDataRecord,
        audit: MasterDataAudit,
        expected_revision: int,
    ) -> None:
        with Session(self._engine) as session, session.begin():
            result = session.execute(
                update(MasterDataRecordRow)
                .where(
                    MasterDataRecordRow.catalog == record.catalog.value,
                    MasterDataRecordRow.code == record.code,
                    MasterDataRecordRow.revision == expected_revision,
                )
                .values(
                    display_name=record.display_name,
                    attributes=record.attributes,
                    active=record.active,
                    revision=record.revision,
                    updated_at=record.updated_at,
                    updated_by=record.updated_by,
                )
            )
            if getattr(result, "rowcount", None) != 1:
                current = session.get(MasterDataRecordRow, (record.catalog.value, record.code))
                if current is None:
                    raise MasterDataNotFound(record.code)
                raise MasterDataRevisionConflict(expected_revision, current.revision)
            session.add(_audit_row(audit))

    def list_audits(self, catalog: MasterDataCatalog, code: str) -> list[MasterDataAudit]:
        statement = (
            select(MasterDataAuditRow)
            .where(
                MasterDataAuditRow.catalog == catalog.value,
                MasterDataAuditRow.code == code,
            )
            .order_by(
                MasterDataAuditRow.revision,
                MasterDataAuditRow.timestamp,
                MasterDataAuditRow.audit_id,
            )
        )
        with Session(self._engine) as session:
            return [_audit(row) for row in session.scalars(statement)]

    def is_active(self, catalog: MasterDataCatalog, code: str) -> bool:
        with Session(self._engine) as session:
            return bool(
                session.scalar(
                    select(MasterDataRecordRow.active).where(
                        MasterDataRecordRow.catalog == catalog.value,
                        MasterDataRecordRow.code == code,
                    )
                )
            )


def _record(row: MasterDataRecordRow) -> MasterDataRecord:
    return MasterDataRecord(
        catalog=MasterDataCatalog(row.catalog),
        code=row.code,
        display_name=row.display_name,
        attributes=dict(row.attributes),
        active=row.active,
        revision=row.revision,
        created_at=row.created_at,
        updated_at=row.updated_at,
        created_by=row.created_by,
        updated_by=row.updated_by,
    )


def _record_row(record: MasterDataRecord) -> MasterDataRecordRow:
    return MasterDataRecordRow(
        catalog=record.catalog.value,
        code=record.code,
        display_name=record.display_name,
        attributes=record.attributes,
        active=record.active,
        revision=record.revision,
        created_at=record.created_at,
        updated_at=record.updated_at,
        created_by=record.created_by,
        updated_by=record.updated_by,
    )


def _audit(row: MasterDataAuditRow) -> MasterDataAudit:
    return MasterDataAudit(
        audit_id=row.audit_id,
        catalog=MasterDataCatalog(row.catalog),
        code=row.code,
        revision=row.revision,
        event_type=row.event_type,
        actor_id=row.actor_id,
        timestamp=row.timestamp,
        before=dict(row.before) if row.before is not None else None,
        after=dict(row.after) if row.after is not None else None,
        reason=row.reason,
    )


def _audit_row(audit: MasterDataAudit) -> MasterDataAuditRow:
    return MasterDataAuditRow(
        audit_id=audit.audit_id,
        catalog=audit.catalog.value,
        code=audit.code,
        revision=audit.revision,
        event_type=audit.event_type,
        actor_id=audit.actor_id,
        timestamp=audit.timestamp,
        before=audit.before,
        after=audit.after,
        reason=audit.reason,
    )
