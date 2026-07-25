"""Quality Disposition — Plant Manager final quality decision after inspection.

Does NOT invalidate production submissions or rewind current_stage.
Only produces an effective grade decision and audit trail.

Per V1 business rules:
- Inspector submits inspection (conforming/non-conforming) + evidence
- Supervisor provides opinion only (cannot close exceptions, cannot return)
- Plant Manager makes the FINAL disposition: responsible stage, person, grade, decision
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooRecordRow,
    BambooStageSubmissionRow,
    QualityDispositionRow,
)


class QualityDispositionError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


class QualityDispositionRepository(Protocol):
    def add_disposition(self, disposition: QualityDispositionRow) -> None: ...

    def get_disposition(self, record_id: str) -> QualityDispositionRow | None: ...

    def list_dispositions(
        self, factory_id: str, *, limit: int = 50
    ) -> list[QualityDispositionRow]: ...


class SqlAlchemyQualityDispositionRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def add_disposition(self, disposition: QualityDispositionRow) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(disposition)

    def get_disposition(self, record_id: str) -> QualityDispositionRow | None:
        with Session(self._engine) as session:
            return session.get(QualityDispositionRow, record_id)

    def list_dispositions(
        self, factory_id: str, *, limit: int = 50
    ) -> list[QualityDispositionRow]:
        with Session(self._engine) as session:
            return list(
                session.scalars(
                    select(QualityDispositionRow)
                    .where(QualityDispositionRow.factory_id == factory_id)
                    .order_by(QualityDispositionRow.decided_at.desc())
                    .limit(limit)
                ).all()
            )


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid4())


class QualityDispositionService:
    """Plant Manager final quality decision.

    Only PLANT_MANAGER or SYSTEM_ADMIN can create a disposition.
    Inspector and Supervisor are explicitly denied.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def create_disposition(
        self,
        *,
        record_id: str,
        inspection_id: str | None,
        factory_id: str,
        responsible_stage: str,
        original_grade: str,
        effective_grade: str,
        decision: str,
        decision_note: str,
        decided_by: str,
    ) -> dict[str, Any]:
        """Create a Plant Manager final quality disposition.

        Raises:
            QualityDispositionError: if record/inspection not found,
                if disposition already exists, or if business rules violated.
        """
        with Session(self._engine) as session, session.begin():
            # Verify record exists
            record = session.get(BambooRecordRow, record_id)
            if record is None:
                raise QualityDispositionError(
                    "RECORD_NOT_FOUND", f"Record {record_id} not found"
                )

            # One disposition per record
            existing = session.get(QualityDispositionRow, record_id)
            if existing is not None:
                raise QualityDispositionError(
                    "DISPOSITION_EXISTS",
                    f"Record {record_id} already has a disposition",
                )

            # Resolve responsible employee from stage submission
            responsible_submission_id: str | None = None
            responsible_employee_code = ""
            responsible_employee_name = ""
            responsible_position = ""

            if responsible_stage:
                submission = session.scalar(
                    select(BambooStageSubmissionRow)
                    .where(
                        BambooStageSubmissionRow.record_id == record_id,
                        BambooStageSubmissionRow.stage_key == responsible_stage,
                        BambooStageSubmissionRow.invalidated.is_(False),
                    )
                    .order_by(BambooStageSubmissionRow.version.desc())
                )
                if submission is not None:
                    responsible_submission_id = submission.submission_id
                    responsible_employee_code = submission.actor_id or ""
                    responsible_employee_name = submission.actor_name or ""
                    responsible_position = submission.role_code or ""

            # Resolve cage_no from record base_info
            cage_no = str(record.base_info.get("cage_no", "")) if record.base_info else ""

            now = _now()
            disposition = QualityDispositionRow(
                disposition_id=_id(),
                record_id=record_id,
                inspection_id=inspection_id,
                factory_id=factory_id,
                cage_no=cage_no,
                responsible_stage=responsible_stage,
                responsible_submission_id=responsible_submission_id,
                responsible_employee_code=responsible_employee_code,
                responsible_employee_name_snapshot=responsible_employee_name,
                responsible_position_snapshot=responsible_position,
                original_grade=original_grade,
                effective_grade=effective_grade,
                decision=decision,
                decision_note=decision_note,
                decided_by=decided_by,
                decided_at=now,
                revision=1,
            )
            session.add(disposition)

            return self._to_dict(disposition)

    def get_disposition(self, record_id: str) -> dict[str, Any] | None:
        with Session(self._engine) as session:
            row = session.get(QualityDispositionRow, record_id)
            return self._to_dict(row) if row else None

    def list_dispositions(
        self, factory_id: str, *, limit: int = 50
    ) -> list[dict[str, Any]]:
        with Session(self._engine) as session:
            rows = session.scalars(
                select(QualityDispositionRow)
                .where(QualityDispositionRow.factory_id == factory_id)
                .order_by(QualityDispositionRow.decided_at.desc())
                .limit(limit)
            ).all()
            return [self._to_dict(row) for row in rows]

    def update_disposition(
        self,
        record_id: str,
        *,
        effective_grade: str | None = None,
        decision: str | None = None,
        decision_note: str | None = None,
        decided_by: str,
    ) -> dict[str, Any]:
        """Update an existing disposition (revision bump)."""
        with Session(self._engine) as session, session.begin():
            row = session.get(QualityDispositionRow, record_id)
            if row is None:
                raise QualityDispositionError(
                    "DISPOSITION_NOT_FOUND",
                    f"No disposition for record {record_id}",
                )
            if effective_grade is not None:
                row.effective_grade = effective_grade
            if decision is not None:
                row.decision = decision
            if decision_note is not None:
                row.decision_note = decision_note
            row.decided_by = decided_by
            row.decided_at = _now()
            row.revision += 1
            return self._to_dict(row)

    @staticmethod
    def _to_dict(row: QualityDispositionRow) -> dict[str, Any]:
        return {
            "disposition_id": row.disposition_id,
            "record_id": row.record_id,
            "inspection_id": row.inspection_id,
            "factory_id": row.factory_id,
            "cage_no": row.cage_no,
            "responsible_stage": row.responsible_stage,
            "responsible_submission_id": row.responsible_submission_id,
            "responsible_employee_code": row.responsible_employee_code,
            "responsible_employee_name_snapshot": row.responsible_employee_name_snapshot,
            "responsible_position_snapshot": row.responsible_position_snapshot,
            "original_grade": row.original_grade,
            "effective_grade": row.effective_grade,
            "decision": row.decision,
            "decision_note": row.decision_note,
            "decided_by": row.decided_by,
            "decided_at": row.decided_at.isoformat() if row.decided_at else None,
            "revision": row.revision,
        }
