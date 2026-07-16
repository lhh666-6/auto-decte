"""SQLAlchemy repository implementations."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC
from uuid import uuid4

from sqlalchemy import Engine, delete, func, literal_column, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    AIReviewRow,
    AuditEventRow,
    EvidenceFileRow,
    ExportBatchRow,
    FormFieldRow,
    FormRow,
    RecognitionAttemptRow,
    RecordVersionRow,
    ReviewDraftRow,
    ReviewLeaseRow,
    TaskEventRow,
    TaskRow,
)
from app.domain.models import (
    AIReviewRecord,
    AIStatus,
    AuditEvent,
    EvidenceFile,
    EvidenceType,
    ExportBatch,
    ExportStatus,
    Form,
    FormField,
    RecognitionAttempt,
    RecordStatus,
    RecordVersion,
    ReviewStatus,
    ValueSource,
    thaw_json,
)
from app.modules.tasks.models_ds import TaskStatus


class SqlAlchemyFormRepository:
    def __init__(self, engine: Engine, session: Session | None = None) -> None:
        self._engine = engine
        self._session = session

    def with_session(self, session: Session) -> "SqlAlchemyFormRepository":
        """Bind this compatible repository facade to an outer transaction."""
        return SqlAlchemyFormRepository(self._engine, session)

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

    def add_form(self, form: Form) -> None:
        with self._transaction() as session:
            session.add(
                FormRow(
                    form_id=form.form_id,
                    template_id=form.template_id,
                    template_version=form.template_version,
                    coordinate_version=form.coordinate_version,
                    review_status=form.review_status.value,
                    export_status=form.export_status.value,
                    current_record_version=form.current_record_version,
                    priority=form.priority,
                    created_at=form.created_at,
                )
            )

    def get_form(self, form_id: str) -> Form | None:
        with self._read_session() as session:
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
                priority=row.priority,
                created_at=row.created_at,
            )

    def list_forms(
        self,
        *,
        review_statuses: tuple[ReviewStatus, ...] = (),
        export_statuses: tuple[ExportStatus, ...] = (),
    ) -> list[Form]:
        """List forms even when they do not yet have a confirmed record version.

        Queue views must include newly imported forms.  ``search_current`` is
        deliberately unsuitable here because it joins the current record
        version and therefore omits forms that are waiting for first review.
        """
        statement = select(FormRow)
        if review_statuses:
            values = [item.value for item in review_statuses]
            statement = statement.where(FormRow.review_status.in_(values))
        if export_statuses:
            values = [item.value for item in export_statuses]
            statement = statement.where(FormRow.export_status.in_(values))
        statement = statement.order_by(
            FormRow.priority.desc(), FormRow.created_at, FormRow.form_id
        )
        with self._read_session() as session:
            return [self._to_form(row) for row in session.scalars(statement).all()]

    def add_record_version(self, version: RecordVersion) -> None:
        with self._transaction() as session:
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
        with self._read_session() as session:
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
        with self._transaction() as session:
            form = session.get(FormRow, form_id)
            if form is None:
                raise KeyError(f"Unknown form: {form_id}")
            form.review_status = status.value

    def set_template(
        self, form_id: str, template_id: str, template_version: str, status: ReviewStatus
    ) -> None:
        with self._transaction() as session:
            form = session.get(FormRow, form_id)
            if form is None:
                raise KeyError(f"Unknown form: {form_id}")
            form.template_id = template_id
            form.template_version = template_version
            form.review_status = status.value

    def set_export_status(self, form_id: str, status: ExportStatus) -> None:
        with self._transaction() as session:
            form = session.get(FormRow, form_id)
            if form is None:
                raise KeyError(f"Unknown form: {form_id}")
            form.export_status = status.value

    def add_evidence(self, evidence: EvidenceFile) -> None:
        with self._transaction() as session:
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

    def add_form_field(self, field: FormField) -> None:
        with self._transaction() as session:
            session.add(
                FormFieldRow(
                    field_id=field.field_id,
                    form_id=field.form_id,
                    field_name=field.field_name,
                    source_region=field.source_region,
                    current_value=field.current_value,
                    current_value_source=(
                        field.current_value_source.value if field.current_value_source else None
                    ),
                    current_record_version=field.current_record_version,
                )
            )

    def list_form_fields(self, form_id: str) -> list[FormField]:
        statement = (
            select(FormFieldRow)
            .where(FormFieldRow.form_id == form_id)
            .order_by(FormFieldRow.field_name, FormFieldRow.field_id)
        )
        with self._read_session() as session:
            rows = session.scalars(statement).all()
            return [
                FormField(
                    field_id=row.field_id,
                    form_id=row.form_id,
                    field_name=row.field_name,
                    source_region=row.source_region,
                    current_value=row.current_value,
                    current_value_source=(
                        ValueSource(row.current_value_source)
                        if row.current_value_source is not None
                        else None
                    ),
                    current_record_version=row.current_record_version,
                )
                for row in rows
            ]

    def add_recognition_attempt(self, attempt: RecognitionAttempt) -> None:
        with self._transaction() as session:
            session.add(
                RecognitionAttemptRow(
                    attempt_id=attempt.attempt_id,
                    field_id=attempt.field_id,
                    engine=attempt.engine,
                    model_version=attempt.model_version,
                    candidate_value=attempt.candidate_value,
                    confidence=attempt.confidence,
                    created_at=attempt.created_at,
                    crop_file_id=attempt.crop_file_id,
                )
            )

    def list_recognition_attempts(self, field_id: str) -> list[RecognitionAttempt]:
        statement = (
            select(RecognitionAttemptRow)
            .where(RecognitionAttemptRow.field_id == field_id)
            .order_by(RecognitionAttemptRow.created_at, RecognitionAttemptRow.attempt_id)
        )
        with self._read_session() as session:
            rows = session.scalars(statement).all()
            return [
                RecognitionAttempt(
                    attempt_id=row.attempt_id,
                    field_id=row.field_id,
                    engine=row.engine,
                    model_version=row.model_version,
                    candidate_value=row.candidate_value,
                    confidence=row.confidence,
                    created_at=row.created_at,
                    crop_file_id=row.crop_file_id,
                )
                for row in rows
            ]

    def list_recognition_attempts_for_form(self, form_id: str) -> list[RecognitionAttempt]:
        statement = (
            select(RecognitionAttemptRow)
            .join(FormFieldRow, FormFieldRow.field_id == RecognitionAttemptRow.field_id)
            .where(FormFieldRow.form_id == form_id)
            .order_by(RecognitionAttemptRow.created_at, RecognitionAttemptRow.attempt_id)
        )
        with self._read_session() as session:
            rows = session.scalars(statement).all()
            return [
                RecognitionAttempt(
                    attempt_id=row.attempt_id,
                    field_id=row.field_id,
                    engine=row.engine,
                    model_version=row.model_version,
                    candidate_value=row.candidate_value,
                    confidence=row.confidence,
                    created_at=row.created_at,
                    crop_file_id=row.crop_file_id,
                )
                for row in rows
            ]

    def find_by_sha256(self, sha256: str) -> EvidenceFile | None:
        statement = select(EvidenceFileRow).where(EvidenceFileRow.sha256 == sha256)
        with self._read_session() as session:
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

    def purge_test_form(self, form_id: str) -> list[str]:
        """Physically remove one local-development form and return stored file URIs."""
        return self._delete_form_data(form_id, delete_tasks=True)

    def rollback_failed_import(self, form_id: str) -> list[str]:
        """Remove partially imported form data while retaining the failed task record."""
        return self._delete_form_data(form_id, delete_tasks=False)

    def _delete_form_data(self, form_id: str, *, delete_tasks: bool) -> list[str]:
        with self._transaction() as session:
            form = session.get(FormRow, form_id)
            if form is None:
                if delete_tasks:
                    raise KeyError(f"Unknown form: {form_id}")
                return []
            field_ids = select(FormFieldRow.field_id).where(FormFieldRow.form_id == form_id)
            task_ids = select(TaskRow.task_id).where(TaskRow.resource_id == form_id)
            uris = list(
                session.scalars(
                    select(EvidenceFileRow.uri).where(EvidenceFileRow.form_id == form_id)
                )
            )
            session.execute(
                delete(RecognitionAttemptRow).where(
                    RecognitionAttemptRow.field_id.in_(field_ids)
                )
            )
            session.execute(delete(ReviewDraftRow).where(ReviewDraftRow.form_id == form_id))
            session.execute(delete(ReviewLeaseRow).where(ReviewLeaseRow.form_id == form_id))
            session.execute(delete(AIReviewRow).where(AIReviewRow.form_id == form_id))
            session.execute(delete(AuditEventRow).where(AuditEventRow.form_id == form_id))
            session.execute(delete(RecordVersionRow).where(RecordVersionRow.form_id == form_id))
            session.execute(delete(FormFieldRow).where(FormFieldRow.form_id == form_id))
            session.execute(delete(EvidenceFileRow).where(EvidenceFileRow.form_id == form_id))
            if delete_tasks:
                session.execute(delete(TaskEventRow).where(TaskEventRow.task_id.in_(task_ids)))
                session.execute(delete(TaskRow).where(TaskRow.resource_id == form_id))
            session.delete(form)
            return uris

    def add_audit_event(self, event: AuditEvent) -> None:
        with self._transaction() as session:
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
            .order_by(AuditEventRow.timestamp, literal_column("audit_events.rowid"))
        )
        with self._read_session() as session:
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

    def list_evidence(self, form_id: str) -> list[EvidenceFile]:
        statement = (
            select(EvidenceFileRow)
            .where(EvidenceFileRow.form_id == form_id)
            .order_by(EvidenceFileRow.created_at, EvidenceFileRow.file_id)
        )
        with self._read_session() as session:
            rows = session.scalars(statement).all()
            return [
                EvidenceFile(
                    file_id=row.file_id,
                    form_id=row.form_id,
                    related_field_id=row.related_field_id,
                    type=EvidenceType(row.type),
                    uri=row.uri,
                    sha256=row.sha256,
                    immutable=row.immutable,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    def search_current(
        self,
        *,
        form_id: str | None = None,
        employee_id: str | None = None,
        work_order_id: str | None = None,
        review_status: ReviewStatus | None = None,
        export_status: ExportStatus | None = None,
    ) -> list[tuple[Form, RecordVersion]]:
        statement = select(FormRow, RecordVersionRow).join(
            RecordVersionRow,
            (RecordVersionRow.form_id == FormRow.form_id)
            & (RecordVersionRow.version == FormRow.current_record_version),
        )
        if form_id is not None:
            statement = statement.where(FormRow.form_id == form_id)
        if employee_id is not None:
            statement = statement.where(
                func.json_extract(RecordVersionRow.values, "$.employee_id") == employee_id
            )
        if work_order_id is not None:
            statement = statement.where(
                func.json_extract(RecordVersionRow.values, "$.work_order_id") == work_order_id
            )
        if review_status is not None:
            statement = statement.where(FormRow.review_status == review_status.value)
        if export_status is not None:
            statement = statement.where(FormRow.export_status == export_status.value)
        statement = statement.order_by(FormRow.form_id)
        with self._read_session() as session:
            rows = session.execute(statement).all()
            return [(self._to_form(form), self._to_record(record)) for form, record in rows]

    def add_export_batch(self, batch: ExportBatch) -> None:
        with self._transaction() as session:
            session.add(self._export_batch_row(batch))

    def complete_export(self, batch: ExportBatch) -> None:
        """Atomically persist an export and mark its exact record versions exported."""
        with self._transaction() as session:
            reexport_records: list[tuple[str, int]] = []
            superseded_row = (
                session.get(ExportBatchRow, batch.supersedes_batch_id)
                if batch.supersedes_batch_id is not None
                else None
            )
            if batch.supersedes_batch_id is not None and superseded_row is None:
                raise KeyError(f"Unknown export batch: {batch.supersedes_batch_id}")
            for form_id, version in batch.included_records:
                form = session.get(FormRow, form_id)
                record = session.scalar(
                    select(RecordVersionRow).where(
                        RecordVersionRow.form_id == form_id,
                        RecordVersionRow.version == version,
                    )
                )
                if form is None or record is None:
                    raise KeyError(f"Unknown record version: {form_id}@{version}")
                if (
                    form.current_record_version != version
                    or form.review_status != ReviewStatus.CONFIRMED.value
                    or record.status
                    not in {RecordStatus.CONFIRMED.value, RecordStatus.CORRECTED.value}
                ):
                    raise ValueError(
                        f"Record is no longer exportable: {form_id}@{version}"
                    )
                if form.export_status == ExportStatus.REEXPORT_REQUIRED.value:
                    reexport_records.append((form_id, version))
            if reexport_records and batch.supersedes_batch_id is None:
                raise ValueError(
                    "supersedes_batch_id is required for REEXPORT_REQUIRED records"
                )
            if superseded_row is not None:
                if not reexport_records:
                    raise ValueError(
                        "supersedes_batch_id is only valid for REEXPORT_REQUIRED records"
                    )
                previous_versions: dict[str, list[int]] = {}
                for old_form_id, old_version in superseded_row.included_records:
                    previous_versions.setdefault(str(old_form_id), []).append(
                        int(old_version)
                    )
                for form_id, version in reexport_records:
                    if not any(
                        old_version < version
                        for old_version in previous_versions.get(form_id, [])
                    ):
                        raise ValueError(
                            "Superseded batch must contain an older version of "
                            f"{form_id}"
                        )
            session.add(self._export_batch_row(batch))
            for form_id, version in batch.included_records:
                form = session.get(FormRow, form_id)
                assert form is not None
                form.export_status = ExportStatus.EXPORTED.value
                session.add(
                    AuditEventRow(
                        event_id=f"EVENT-{uuid4().hex}",
                        form_id=form_id,
                        event_type="EXPORT",
                        actor_id=batch.exported_by,
                        timestamp=batch.exported_at,
                        before=None,
                        after={
                            "export_batch_id": batch.export_batch_id,
                            "record_version": version,
                        },
                        reason=None,
                        evidence_ids=[],
                    )
                )
            if batch.task_id is not None:
                task = session.get(TaskRow, batch.task_id)
                if task is None:
                    raise KeyError(f"Unknown task: {batch.task_id}")
                if task.status != TaskStatus.RUNNING.value:
                    raise ValueError(
                        f"Export task is not running: {batch.task_id}"
                    )
                task.status = TaskStatus.SUCCEEDED.value
                task.progress = 100
                task.error = None
                task.updated_at = batch.exported_at
                sequence = (
                    session.scalar(
                        select(func.max(TaskEventRow.sequence)).where(
                            TaskEventRow.task_id == batch.task_id
                        )
                    )
                    or 0
                ) + 1
                session.add(
                    TaskEventRow(
                        event_id=f"TASK-EVENT-{uuid4().hex}",
                        task_id=batch.task_id,
                        sequence=sequence,
                        event_type=TaskStatus.SUCCEEDED.value,
                        progress=100,
                        step=task.step,
                        detail={"export_batch_id": batch.export_batch_id},
                        created_at=batch.exported_at,
                    )
                )

    def get_export_batch(self, batch_id: str) -> ExportBatch | None:
        with self._read_session() as session:
            row = session.get(ExportBatchRow, batch_id)
            return self._to_export_batch(row) if row is not None else None

    @staticmethod
    def _export_batch_row(batch: ExportBatch) -> ExportBatchRow:
        return ExportBatchRow(
            export_batch_id=batch.export_batch_id,
            export_type=batch.export_type,
            task_id=batch.task_id,
            template_snapshot=thaw_json(batch.template_snapshot),
            mapping_snapshot=thaw_json(batch.mapping_snapshot),
            mapping_hash=batch.mapping_hash,
            filters=thaw_json(batch.filters),
            included_records=[list(item) for item in batch.included_records],
            file_path=batch.file_path,
            download_name=batch.download_name,
            file_sha256=batch.file_sha256,
            exported_by=batch.exported_by,
            exported_at=batch.exported_at,
            supersedes_batch_id=batch.supersedes_batch_id,
        )

    def get_export_batch_by_task(self, task_id: str) -> ExportBatch | None:
        statement = select(ExportBatchRow).where(ExportBatchRow.task_id == task_id)
        with self._read_session() as session:
            row = session.scalar(statement)
            return self._to_export_batch(row) if row is not None else None

    def list_export_batches(self) -> list[ExportBatch]:
        statement = select(ExportBatchRow).order_by(
            ExportBatchRow.exported_at.desc(), ExportBatchRow.export_batch_id.desc()
        )
        with self._read_session() as session:
            rows = session.scalars(statement).all()
            return [self._to_export_batch(row) for row in rows]

    def add_ai_review(self, review: AIReviewRecord) -> None:
        with self._transaction() as session:
            session.add(
                AIReviewRow(
                    review_id=review.review_id,
                    form_id=review.form_id,
                    status=review.status.value,
                    payload=review.payload,
                    created_at=review.created_at,
                )
            )

    def list_ai_reviews(self, form_id: str) -> list[AIReviewRecord]:
        statement = (
            select(AIReviewRow)
            .where(AIReviewRow.form_id == form_id)
            .order_by(AIReviewRow.created_at, AIReviewRow.review_id)
        )
        with self._read_session() as session:
            rows = session.scalars(statement).all()
            return [
                AIReviewRecord(
                    review_id=row.review_id,
                    form_id=row.form_id,
                    status=AIStatus(row.status),
                    payload=row.payload,
                    created_at=row.created_at,
                )
                for row in rows
            ]

    @staticmethod
    def _to_form(row: FormRow) -> Form:
        return Form(
            form_id=row.form_id,
            template_id=row.template_id,
            template_version=row.template_version,
            coordinate_version=row.coordinate_version,
            review_status=ReviewStatus(row.review_status),
            export_status=ExportStatus(row.export_status),
            current_record_version=row.current_record_version,
            priority=row.priority,
            created_at=row.created_at,
        )

    @staticmethod
    def _to_record(row: RecordVersionRow) -> RecordVersion:
        return RecordVersion(
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

    @staticmethod
    def _to_export_batch(row: ExportBatchRow) -> ExportBatch:
        exported_at = row.exported_at
        if exported_at.tzinfo is None:
            exported_at = exported_at.replace(tzinfo=UTC)
        return ExportBatch(
            export_batch_id=row.export_batch_id,
            export_type=row.export_type,
            filters=row.filters,
            included_records=tuple(
                (str(form_id), int(version)) for form_id, version in row.included_records
            ),
            file_path=row.file_path,
            file_sha256=row.file_sha256,
            exported_by=row.exported_by,
            exported_at=exported_at,
            supersedes_batch_id=row.supersedes_batch_id,
            task_id=row.task_id,
            template_snapshot=row.template_snapshot,
            mapping_snapshot=tuple(row.mapping_snapshot),
            mapping_hash=row.mapping_hash,
            download_name=row.download_name,
        )
