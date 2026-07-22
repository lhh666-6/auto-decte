"""SQLAlchemy persistence for the bamboo production workflow."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Engine, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooRecordRow,
    BambooSignatureRow,
    BambooStageSubmissionRow,
)
from app.modules.bamboo_process.errors_ds import StaleBambooRevision
from app.modules.bamboo_process.models_ds import (
    BambooRecord,
    BambooRecordStatus,
    BambooStage,
    ElectronicSignature,
    StageSubmission,
)


class SqlAlchemyBambooProcessRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def next_display_sequence(self, factory_id: str, production_date: str) -> int:
        date_token = production_date.replace("-", "")
        with Session(self._engine) as session:
            count = session.scalar(
                select(func.count())
                .select_from(BambooRecordRow)
                .where(
                    BambooRecordRow.factory_id == factory_id,
                    BambooRecordRow.display_no.like(f"ZS-{date_token}-%"),
                )
            )
        return int(count or 0) + 1

    def add(self, record: BambooRecord) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(_record_row(record))

    def get(self, record_id: str) -> BambooRecord | None:
        with Session(self._engine) as session:
            row = session.get(BambooRecordRow, record_id)
            if row is None:
                return None
            submissions = session.scalars(
                select(BambooStageSubmissionRow)
                .where(BambooStageSubmissionRow.record_id == record_id)
                .order_by(
                    BambooStageSubmissionRow.submitted_at,
                    BambooStageSubmissionRow.stage_key,
                    BambooStageSubmissionRow.version,
                )
            ).all()
            return _record(row, submissions)

    def find_idempotent_result(
        self,
        actor_id: str,
        idempotency_key: str,
    ) -> BambooRecord | None:
        with Session(self._engine) as session:
            signature = session.scalar(
                select(BambooSignatureRow).where(
                    BambooSignatureRow.actor_id == actor_id,
                    BambooSignatureRow.idempotency_key == idempotency_key,
                )
            )
            if signature is None:
                return None
            submission = session.get(
                BambooStageSubmissionRow,
                signature.submission_id,
            )
            record_id = submission.record_id if submission is not None else None
        return self.get(record_id) if record_id is not None else None

    def append_stage(
        self,
        *,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
        expected_revision: int,
    ) -> BambooRecord:
        with Session(self._engine) as session, session.begin():
            result = cast(
                CursorResult[Any],
                session.execute(
                    update(BambooRecordRow)
                    .where(
                        BambooRecordRow.record_id == record.record_id,
                        BambooRecordRow.revision == expected_revision,
                    )
                    .values(
                        current_stage=(
                            record.current_stage.value
                            if record.current_stage is not None
                            else None
                        ),
                        status=record.status.value,
                        revision=record.revision,
                        updated_at=record.updated_at,
                    )
                ),
            )
            if result.rowcount != 1:
                actual = session.scalar(
                    select(BambooRecordRow.revision).where(
                        BambooRecordRow.record_id == record.record_id
                    )
                )
                raise StaleBambooRevision(expected_revision, int(actual or 0))
            session.add(_submission_row(submission))
            session.flush()
            session.add(_signature_row(signature))
        stored = self.get(record.record_id)
        if stored is None:  # pragma: no cover - guarded by the successful update
            raise RuntimeError("bamboo record disappeared after stage submission")
        return stored


def _record_row(record: BambooRecord) -> BambooRecordRow:
    return BambooRecordRow(
        record_id=record.record_id,
        display_no=record.display_no,
        factory_id=record.factory_id,
        source_type=record.source_type,
        source_ref=record.source_ref,
        base_info=record.base_info,
        current_stage=(record.current_stage.value if record.current_stage else None),
        status=record.status.value,
        revision=record.revision,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _submission_row(submission: StageSubmission) -> BambooStageSubmissionRow:
    return BambooStageSubmissionRow(
        submission_id=submission.submission_id,
        record_id=submission.record_id,
        stage_key=submission.stage.value,
        version=submission.version,
        values=submission.values,
        actor_id=submission.actor_id,
        actor_name=submission.actor_name,
        role_code=submission.role_code,
        factory_id=submission.factory_id,
        submitted_at=submission.submitted_at,
        invalidated=submission.invalidated,
    )


def _signature_row(signature: ElectronicSignature) -> BambooSignatureRow:
    return BambooSignatureRow(
        signature_id=signature.signature_id,
        submission_id=signature.submission_id,
        actor_id=signature.actor_id,
        employee_code=signature.employee_code,
        actor_name=signature.actor_name,
        factory_id=signature.factory_id,
        role_code=signature.role_code,
        payload_hash=signature.payload_hash,
        signed_at=signature.signed_at,
        device_id=signature.device_id,
        request_id=signature.request_id,
        idempotency_key=signature.idempotency_key,
    )


def _record(
    row: BambooRecordRow,
    submissions: Sequence[BambooStageSubmissionRow],
) -> BambooRecord:
    return BambooRecord(
        record_id=row.record_id,
        display_no=row.display_no,
        factory_id=row.factory_id,
        source_type=row.source_type,
        source_ref=row.source_ref,
        base_info=dict(row.base_info),
        current_stage=(BambooStage(row.current_stage) if row.current_stage else None),
        status=BambooRecordStatus(row.status),
        revision=row.revision,
        created_by=row.created_by,
        created_at=_utc(row.created_at),
        updated_at=_utc(row.updated_at),
        submissions=tuple(_submission(item) for item in submissions),
    )


def _submission(row: BambooStageSubmissionRow) -> StageSubmission:
    return StageSubmission(
        submission_id=row.submission_id,
        record_id=row.record_id,
        stage=BambooStage(row.stage_key),
        version=row.version,
        values=dict(row.values),
        actor_id=row.actor_id,
        actor_name=row.actor_name,
        role_code=row.role_code,
        factory_id=row.factory_id,
        submitted_at=_utc(row.submitted_at),
        invalidated=row.invalidated,
    )


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value
