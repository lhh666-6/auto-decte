"""Quality Disposition — Plant Manager final quality decision after inspection.

Does NOT invalidate production submissions or rewind current_stage.
Only produces an effective grade decision and audit trail.

Per V1 business rules:
- Inspector submits inspection (conforming/non-conforming) + evidence
- Supervisor provides opinion only (cannot close exceptions, cannot return)
- Plant Manager makes the FINAL disposition: responsible stage, person, grade, decision

V1 Runtime Closure fixes (P0-01 through P0-05):
- P0-02: Query by record_id via select().where(), NOT session.get() (PK is disposition_id)
- P0-03: Resolve factory_id, original_grade, cage_no SERVER-SIDE from BambooRecord
- P0-05: Full electronic signature snapshot (decided_by, decided_at, revision, payload hash)
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooInspectionExceptionRow,
    BambooInspectionRow,
    BambooRecordRow,
    BambooStageSubmissionRow,
    QualityDispositionRow,
)
from app.modules.bamboo_process.models_ds import BambooFormType, BambooStage

# ── Valid effective grades ──
VALID_GRADES = {"A", "B"}

# ── Valid disposition decisions ──
VALID_DECISIONS = {"CONFIRMED", "DOWNGRADED", "UPGRADED"}

# ── Production stages per form type (where quality issues originate) ──
FORM_PRODUCTION_STAGES: dict[str, set[str]] = {
    BambooFormType.SORTING.value: {BambooStage.SORT.value},
    BambooFormType.DIPPING_DRYING.value: {
        BambooStage.DIPPING.value,
        BambooStage.DRYING.value,
    },
}


class QualityDispositionError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _now() -> datetime:
    return datetime.now(UTC)


def _id() -> str:
    return str(uuid4())


def _compute_signature_payload(disposition: QualityDispositionRow) -> str:
    """Compute a deterministic hash of the disposition for signature evidence."""
    canonical = json.dumps(
        {
            "disposition_id": disposition.disposition_id,
            "record_id": disposition.record_id,
            "inspection_id": disposition.inspection_id,
            "factory_id": disposition.factory_id,
            "cage_no": disposition.cage_no,
            "responsible_stage": disposition.responsible_stage,
            "responsible_submission_id": disposition.responsible_submission_id,
            "responsible_employee_code": disposition.responsible_employee_code,
            "original_grade": disposition.original_grade,
            "effective_grade": disposition.effective_grade,
            "decision": disposition.decision,
            "decision_note": disposition.decision_note,
            "decided_by": disposition.decided_by,
            "decided_at": disposition.decided_at.isoformat() if disposition.decided_at else None,
            "revision": disposition.revision,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


class QualityDispositionService:
    """Plant Manager final quality decision.

    Only PLANT_MANAGER or SYSTEM_ADMIN can create/update a disposition.
    Inspector and Supervisor are explicitly denied.
    """

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    # ── P0-02 fix: query by record_id using select().where(), not session.get() ──

    @staticmethod
    def _get_by_record_id(
        session: Session, record_id: str
    ) -> QualityDispositionRow | None:
        """Look up disposition by record_id (NOT primary key)."""
        return session.scalar(
            select(QualityDispositionRow).where(
                QualityDispositionRow.record_id == record_id
            )
        )

    # ── P0-03 fix: server-side authoritative data resolution ──

    def _resolve_record_authority(
        self, session: Session, record_id: str
    ) -> BambooRecordRow:
        """Resolve the BambooRecord and validate it exists."""
        record = session.get(BambooRecordRow, record_id)
        if record is None:
            raise QualityDispositionError(
                "RECORD_NOT_FOUND", f"生产记录 {record_id} 不存在"
            )
        return record

    def _resolve_original_grade(self, record: BambooRecordRow) -> str:
        """Resolve original grade from the authoritative record base_info."""
        grade = ""
        if record.base_info:
            grade = str(record.base_info.get("grade", "")).strip()
        if not grade:
            raise QualityDispositionError(
                "GRADE_NOT_FOUND",
                f"记录 {record.record_id} 未找到原评级，无法创建质量处置",
            )
        return grade

    def _resolve_cage_no(self, record: BambooRecordRow) -> str:
        """Resolve cage_no from record base_info."""
        if record.base_info:
            return str(record.base_info.get("cage_no", ""))
        return ""

    def _validate_stage_for_form(
        self, responsible_stage: str, form_type: str
    ) -> None:
        """Validate that responsible_stage is a valid production stage for this form."""
        valid_stages = FORM_PRODUCTION_STAGES.get(form_type, set())
        if responsible_stage not in valid_stages:
            raise QualityDispositionError(
                "INVALID_RESPONSIBLE_STAGE",
                f"责任环节 {responsible_stage!r} 不属于表单类型 {form_type}，"
                f"有效值: {sorted(valid_stages)}",
            )

    def _resolve_responsible_employee(
        self, session: Session, record_id: str, responsible_stage: str
    ) -> dict[str, str]:
        """Resolve responsible employee from the stage submission snapshot."""
        submission = session.scalar(
            select(BambooStageSubmissionRow)
            .where(
                BambooStageSubmissionRow.record_id == record_id,
                BambooStageSubmissionRow.stage_key == responsible_stage,
                BambooStageSubmissionRow.invalidated.is_(False),
            )
            .order_by(BambooStageSubmissionRow.version.desc())
        )
        if submission is None:
            raise QualityDispositionError(
                "NO_VALID_SUBMISSION",
                f"记录 {record_id} 在环节 {responsible_stage} 没有有效提交，"
                f"无法确定责任人员",
            )
        return {
            "submission_id": submission.submission_id,
            "employee_code": submission.actor_id or "",
            "employee_name": submission.actor_name or "",
            "position": submission.role_code or "",
        }

    def create_disposition(
        self,
        *,
        record_id: str,
        inspection_id: str | None,
        responsible_stage: str,
        effective_grade: str,
        decision: str,
        decision_note: str,
        decided_by: str,
        decided_by_name: str = "",
        decided_by_factory: str = "",
        decided_by_position: str = "",
    ) -> dict[str, Any]:
        """Create a Plant Manager final quality disposition.

        P0-03: factory_id, original_grade, cage_no, and responsible_employee
        are ALL resolved server-side from the BambooRecord and its submissions.
        The client only provides: record_id, inspection_id, responsible_stage,
        effective_grade, decision, decision_note.

        Raises:
            QualityDispositionError: on any business rule violation.
        """
        # ── Validate inputs ──
        if effective_grade not in VALID_GRADES:
            raise QualityDispositionError(
                "INVALID_GRADE",
                f"最终评级必须是 A 或 B，收到: {effective_grade!r}",
            )
        if decision not in VALID_DECISIONS:
            raise QualityDispositionError(
                "INVALID_DECISION",
                f"处置结论无效: {decision!r}，有效值: {sorted(VALID_DECISIONS)}",
            )
        if not decision_note or not decision_note.strip():
            raise QualityDispositionError(
                "DECISION_NOTE_REQUIRED",
                "处置说明不能为空",
            )

        with Session(self._engine) as session, session.begin():
            # ── P0-03: Resolve record (server-side authority) ──
            record = self._resolve_record_authority(session, record_id)

            # ── 1.4: Factory isolation check ──
            # Plant Manager can only create dispositions for their own factory.
            # Admin (empty decided_by_factory) skips this check.
            if decided_by_factory and decided_by_factory != record.factory_id:
                raise QualityDispositionError(
                    "CROSS_FACTORY_FORBIDDEN",
                    f"厂长 {decided_by!r} 属于工厂 {decided_by_factory!r}，"
                    f"不能为工厂 {record.factory_id!r} 的记录创建质量处置",
                )

            # ── Resolve factory_id from record (NOT from client) ──
            factory_id = record.factory_id

            # ── Resolve original_grade from record (NOT from client) ──
            original_grade = self._resolve_original_grade(record)

            # ── Resolve cage_no from record ──
            cage_no = self._resolve_cage_no(record)

            # ── 1.5: Inspection ID validation ──
            if inspection_id:
                inspection = session.get(BambooInspectionRow, inspection_id)
                if inspection is None:
                    raise QualityDispositionError(
                        "INSPECTION_NOT_FOUND",
                        f"检测记录 {inspection_id!r} 不存在",
                    )
                if inspection.record_id != record_id:
                    raise QualityDispositionError(
                        "INSPECTION_MISMATCH",
                        f"检测记录 {inspection_id!r} 不属于记录 {record_id!r}，"
                        f"实际属于记录 {inspection.record_id!r}",
                    )
                if inspection.factory_id != record.factory_id:
                    raise QualityDispositionError(
                        "INSPECTION_MISMATCH",
                        f"检测记录 {inspection_id!r} 的工厂 {inspection.factory_id!r} 与"
                        f"记录 {record_id!r} 的工厂 {record.factory_id!r} 不匹配",
                    )

            # ── Validate responsible_stage belongs to this form ──
            self._validate_stage_for_form(responsible_stage, record.form_type)

            # ── Resolve responsible employee from submission snapshot ──
            resp = self._resolve_responsible_employee(
                session, record_id, responsible_stage
            )

            # ── P0-02 fix: check existing by record_id (NOT session.get) ──
            existing = self._get_by_record_id(session, record_id)
            if existing is not None:
                raise QualityDispositionError(
                    "DISPOSITION_EXISTS",
                    f"记录 {record_id} 已有质量处置，请使用更新接口",
                )

            now = _now()
            disposition = QualityDispositionRow(
                disposition_id=_id(),
                record_id=record_id,
                inspection_id=inspection_id,
                factory_id=factory_id,
                cage_no=cage_no,
                responsible_stage=responsible_stage,
                responsible_submission_id=resp["submission_id"],
                responsible_employee_code=resp["employee_code"],
                responsible_employee_name_snapshot=resp["employee_name"],
                responsible_position_snapshot=resp["position"],
                original_grade=original_grade,
                effective_grade=effective_grade,
                decision=decision,
                decision_note=decision_note.strip(),
                decided_by=decided_by,
                decided_at=now,
                revision=1,
            )
            # ── P0-05: Compute and store signature payload hash ──
            disposition.signature_hash = _compute_signature_payload(disposition)

            session.add(disposition)
            session.flush()

            # ── Task 2: Close open inspection exceptions for this disposition ──
            self._close_inspection_exceptions(
                session, record_id, decided_by, now
            )

            return self._to_dict(disposition)

    def get_disposition(
        self, record_id: str, *, actor_factory_id: str | None = None
    ) -> dict[str, Any] | None:
        """Get disposition by record_id.

        P0-04: When actor_factory_id is provided, verify the disposition
        belongs to the actor's factory.
        """
        with Session(self._engine) as session:
            row = self._get_by_record_id(session, record_id)
            if row is None:
                return None
            # P0-04: factory-scoped access check
            if actor_factory_id is not None and row.factory_id != actor_factory_id:
                return None  # Not authorized — treat as not found
            return self._to_dict(row)

    def list_dispositions(
        self,
        factory_id: str,
        *,
        limit: int = 50,
        actor_factory_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List dispositions for a factory.

        P0-04: Plant Manager can only list their own factory.
        Admin can list any factory.
        """
        # P0-04: enforce factory-scoped access
        effective_factory = (
            actor_factory_id if actor_factory_id is not None else factory_id
        )
        with Session(self._engine) as session:
            rows = session.scalars(
                select(QualityDispositionRow)
                .where(QualityDispositionRow.factory_id == effective_factory)
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
        decided_by_name: str = "",
        decided_by_factory: str = "",
        decided_by_position: str = "",
    ) -> dict[str, Any]:
        """Update an existing disposition (revision bump).

        P0-05: Each update produces a new signature payload hash.
        """
        # ── Validate inputs ──
        if effective_grade is not None and effective_grade not in VALID_GRADES:
            raise QualityDispositionError(
                "INVALID_GRADE",
                f"最终评级必须是 A 或 B，收到: {effective_grade!r}",
            )
        if decision is not None and decision not in VALID_DECISIONS:
            raise QualityDispositionError(
                "INVALID_DECISION",
                f"处置结论无效: {decision!r}，有效值: {sorted(VALID_DECISIONS)}",
            )

        with Session(self._engine) as session, session.begin():
            # P0-02 fix: look up by record_id, not session.get()
            row = self._get_by_record_id(session, record_id)
            if row is None:
                raise QualityDispositionError(
                    "DISPOSITION_NOT_FOUND",
                    f"记录 {record_id} 没有质量处置记录",
                )
            if effective_grade is not None:
                row.effective_grade = effective_grade
            if decision is not None:
                row.decision = decision
            if decision_note is not None:
                if not decision_note.strip():
                    raise QualityDispositionError(
                        "DECISION_NOTE_REQUIRED",
                        "处置说明不能为空",
                    )
                row.decision_note = decision_note.strip()
            row.decided_by = decided_by
            row.decided_at = _now()
            row.revision += 1

            # ── P0-05: Compute and store new signature payload hash ──
            row.signature_hash = _compute_signature_payload(row)

            session.flush()

            # ── Task 2: Close open inspection exceptions for this disposition ──
            self._close_inspection_exceptions(
                session, row.record_id, decided_by, row.decided_at
            )

            return self._to_dict(row)

    # ── Task 2: Exception closure helper ──

    @staticmethod
    def _close_inspection_exceptions(
        session: Session,
        record_id: str,
        closed_by: str,
        now: datetime,
    ) -> None:
        """Close all OPEN inspection exceptions linked to this record.

        Called within the same transaction as disposition save to ensure
        atomicity: either both the disposition and exception closure succeed,
        or neither does.
        """
        exceptions = session.scalars(
            select(BambooInspectionExceptionRow).where(
                BambooInspectionExceptionRow.record_id == record_id,
                BambooInspectionExceptionRow.status == "OPEN",
            )
        ).all()
        for exc in exceptions:
            exc.status = "CLOSED"
            exc.resolution = "DISPOSED"
            exc.closed_by = closed_by
            exc.closed_at = now
            exc.revision += 1

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
            "signature_hash": row.signature_hash,
        }
