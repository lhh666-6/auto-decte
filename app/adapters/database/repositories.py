"""SQLAlchemy repository implementations."""

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import AuditEventRow, EvidenceFileRow, FormRow, RecordVersionRow
from app.domain.models import (
    AuditEvent,
    EvidenceFile,
    EvidenceType,
    ExportStatus,
    Form,
    RecordStatus,
    RecordVersion,
    ReviewStatus,
)


class SqlAlchemyFormRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_form(self, form: Form) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(
                FormRow(
                    form_id=form.form_id,
                    template_id=form.template_id,
                    template_version=form.template_version,
                    coordinate_version=form.coordinate_version,
                    review_status=form.review_status.value,
                    export_status=form.export_status.value,
                    current_record_version=form.current_record_version,
                    created_at=form.created_at,
                )
            )

    def get_form(self, form_id: str) -> Form | None:
        with Session(self._engine) as session:
            row = session.get(FormRow, form_id)
            if row is None:
                return None
            return Form(
                form_id=row.form_id,
                template_id=row.template_id,
                template_version=row.template_version,
                coordinate_version=row.coordinate_version,
                review_status=ReviewStatus(row.review_status),
                export_status=ExportStatus(row.export_status),
                current_record_version=row.current_record_version,
                created_at=row.created_at,
            )

    def add_record_version(self, version: RecordVersion) -> None:
        with Session(self._engine) as session, session.begin():
            form = session.get(FormRow, version.form_id)
            if form is None:
                raise KeyError(f"Unknown form: {version.form_id}")
            if version.version != form.current_record_version + 1:
                raise ValueError("Record versions must be appended sequentially")
            session.add(
                RecordVersionRow(
                    record_id=version.record_id,
                    form_id=version.form_id,
                    version=version.version,
                    previous_version=version.previous_version,
                    status=version.status.value,
                    values=version.values,
                    change_reason=version.change_reason,
                    confirmed_by=version.confirmed_by,
                    created_at=version.created_at,
                )
            )
            form.current_record_version = version.version

    def list_record_versions(self, form_id: str) -> list[RecordVersion]:
        statement = (
            select(RecordVersionRow)
            .where(RecordVersionRow.form_id == form_id)
            .order_by(RecordVersionRow.version)
        )
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [
                RecordVersion(
                    record_id=row.record_id,
                    form_id=row.form_id,
                    version=row.version,
                    previous_version=row.previous_version,
                    status=RecordStatus(row.status),
                    values=row.values,
                    change_reason=row.change_reason,
                    confirmed_by=row.confirmed_by,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    def set_review_status(self, form_id: str, status: ReviewStatus) -> None:
        with Session(self._engine) as session, session.begin():
            form = session.get(FormRow, form_id)
            if form is None:
                raise KeyError(f"Unknown form: {form_id}")
            form.review_status = status.value

    def add_evidence(self, evidence: EvidenceFile) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(
                EvidenceFileRow(
                    file_id=evidence.file_id,
                    form_id=evidence.form_id,
                    related_field_id=evidence.related_field_id,
                    type=evidence.type.value,
                    uri=evidence.uri,
                    sha256=evidence.sha256,
                    immutable=evidence.immutable,
                    created_at=evidence.created_at,
                )
            )

    def find_by_sha256(self, sha256: str) -> EvidenceFile | None:
        statement = select(EvidenceFileRow).where(EvidenceFileRow.sha256 == sha256)
        with Session(self._engine) as session:
            row = session.scalar(statement)
            if row is None:
                return None
            return EvidenceFile(
                file_id=row.file_id,
                form_id=row.form_id,
                related_field_id=row.related_field_id,
                type=EvidenceType(row.type),
                uri=row.uri,
                sha256=row.sha256,
                immutable=row.immutable,
                created_at=row.created_at,
            )

    def add_audit_event(self, event: AuditEvent) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(
                AuditEventRow(
                    event_id=event.event_id,
                    form_id=event.form_id,
                    event_type=event.event_type,
                    actor_id=event.actor_id,
                    timestamp=event.timestamp,
                    before=event.before,
                    after=event.after,
                    reason=event.reason,
                    evidence_ids=list(event.evidence_ids),
                )
            )

    def list_audit_events(self, form_id: str) -> list[AuditEvent]:
        statement = (
            select(AuditEventRow)
            .where(AuditEventRow.form_id == form_id)
            .order_by(AuditEventRow.timestamp, AuditEventRow.event_id)
        )
        with Session(self._engine) as session:
            rows = session.scalars(statement).all()
            return [
                AuditEvent(
                    event_id=row.event_id,
                    form_id=row.form_id,
                    event_type=row.event_type,
                    actor_id=row.actor_id,
                    timestamp=row.timestamp,
                    before=row.before,
                    after=row.after,
                    reason=row.reason,
                    evidence_ids=tuple(row.evidence_ids),
                )
                for row in rows
            ]
