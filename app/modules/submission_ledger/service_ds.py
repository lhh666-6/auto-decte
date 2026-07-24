"""Immutable finance ledger, correction chains, projections and business tasks."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import Engine, delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BusinessTaskRow,
    FinanceEffectiveRecordRow,
    FinanceLedgerEventRow,
    SubmissionCorrectionRow,
)

SHANGHAI = ZoneInfo("Asia/Shanghai")


class SubmissionLedgerError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


class SubmissionLedgerService:
    def __init__(
        self,
        engine: Engine,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._engine = engine
        self._clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def business_date(value: datetime) -> str:
        aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
        return aware.astimezone(SHANGHAI).date().isoformat()

    def record_acceptance(
        self,
        *,
        submission_id: str,
        factory_id: str,
        subject_employee_code: str,
        actor_id: str,
        definition_version_id: str,
        values: dict[str, Any],
        submitted_at: datetime,
        session: Session | None = None,
    ) -> None:
        if session is not None:
            self._record_acceptance(
                session,
                submission_id=submission_id,
                factory_id=factory_id,
                subject_employee_code=subject_employee_code,
                actor_id=actor_id,
                definition_version_id=definition_version_id,
                values=values,
                submitted_at=submitted_at,
            )
            return
        with Session(self._engine) as owned:
            self._record_acceptance(
                owned,
                submission_id=submission_id,
                factory_id=factory_id,
                subject_employee_code=subject_employee_code,
                actor_id=actor_id,
                definition_version_id=definition_version_id,
                values=values,
                submitted_at=submitted_at,
            )
            try:
                owned.commit()
            except IntegrityError:
                owned.rollback()
                if owned.scalar(
                    select(FinanceLedgerEventRow.event_id).where(
                        FinanceLedgerEventRow.event_type == "SUBMISSION_ACCEPTED",
                        FinanceLedgerEventRow.submission_id == submission_id,
                    )
                ):
                    return
                raise

    def _record_acceptance(
        self,
        session: Session,
        *,
        submission_id: str,
        factory_id: str,
        subject_employee_code: str,
        actor_id: str,
        definition_version_id: str,
        values: dict[str, Any],
        submitted_at: datetime,
    ) -> None:
        if session.scalar(
            select(FinanceLedgerEventRow.event_id).where(
                FinanceLedgerEventRow.event_type == "SUBMISSION_ACCEPTED",
                FinanceLedgerEventRow.submission_id == submission_id,
            )
        ):
            return
        date_value = self.business_date(submitted_at)
        payload = {
            "subject_employee_code": subject_employee_code,
            "definition_version_id": definition_version_id,
            "submitted_at": submitted_at.isoformat(),
            "values": values,
        }
        session.add(
            FinanceLedgerEventRow(
                event_id=self._id("FLE"),
                event_type="SUBMISSION_ACCEPTED",
                submission_id=submission_id,
                root_submission_id=submission_id,
                factory_id=factory_id,
                business_date=date_value,
                payload=payload,
                actor_id=actor_id,
                occurred_at=submitted_at,
            )
        )
        session.add(
            FinanceEffectiveRecordRow(
                root_submission_id=submission_id,
                effective_submission_id=submission_id,
                factory_id=factory_id,
                subject_employee_code=subject_employee_code,
                definition_version_id=definition_version_id,
                business_date=date_value,
                submitted_at=submitted_at,
                values=values,
                status="ACTIVE",
                updated_at=submitted_at,
            )
        )

    @staticmethod
    def _correction_request_hash(
        submission_id: str,
        factory_id: str,
        reason: str,
        requested_by: str,
        assigned_to: str,
    ) -> str:
        """Canonical SHA-256 hash of correction-request fields (no timestamp, no random)."""
        payload = {
            "submission_id": submission_id,
            "factory_id": factory_id,
            "reason": reason.strip(),
            "requested_by": requested_by,
            "assigned_to": assigned_to,
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def return_submission(
        self,
        submission_id: str,
        *,
        factory_id: str,
        reason: str,
        requested_by: str,
        assigned_to: str,
        idempotency_key: str | None = None,
        request_hash: str | None = None,
    ) -> dict[str, str]:
        now = self._clock()
        if idempotency_key:
            request_hash = request_hash or self._correction_request_hash(
                submission_id=submission_id,
                factory_id=factory_id,
                reason=reason,
                requested_by=requested_by,
                assigned_to=assigned_to,
            )
        with Session(self._engine) as session, session.begin():
            projection = session.scalar(
                select(FinanceEffectiveRecordRow).where(
                    FinanceEffectiveRecordRow.effective_submission_id == submission_id
                )
            )
            if projection is None:
                raise SubmissionLedgerError("SUBMISSION_NOT_FOUND", "未找到当前有效提交。")
            if projection.factory_id != factory_id:
                raise SubmissionLedgerError(
                    "CROSS_FACTORY_FORBIDDEN", "厂长只能打回本厂提交。"
                )

            # ── Idempotency check FIRST: see if we already created this correction ──
            if idempotency_key:
                existing = session.scalar(
                    select(SubmissionCorrectionRow).where(
                        SubmissionCorrectionRow.requested_by == requested_by,
                        SubmissionCorrectionRow.idempotency_key == idempotency_key,
                    )
                )
                if existing is not None:
                    if existing.request_hash != request_hash:
                        raise SubmissionLedgerError(
                            "IDEMPOTENCY_CONFLICT",
                            "同一幂等键对应不同更正请求。",
                        )
                    # same hash → replay: return the original correction
                    return {
                        "correction_id": existing.correction_id,
                        "task_id": "",
                        "status": existing.status,
                    }

            # ── Only check CORRECTION_OPEN if not idempotent replay ──
            if session.scalar(
                select(SubmissionCorrectionRow.correction_id).where(
                    SubmissionCorrectionRow.root_submission_id
                    == projection.root_submission_id,
                    SubmissionCorrectionRow.status.in_(("RETURNED", "REPLACED")),
                )
            ):
                raise SubmissionLedgerError("CORRECTION_OPEN", "该提交已有待处理更正。")

            correction_id = self._id("COR")
            task_id = self._id("BT")
            try:
                session.add(
                    SubmissionCorrectionRow(
                        correction_id=correction_id,
                        root_submission_id=projection.root_submission_id,
                        original_submission_id=submission_id,
                        factory_id=factory_id,
                        reason=reason.strip(),
                        delegate_reason="",
                        original_actor_id=projection.subject_employee_code,
                        requested_by=requested_by,
                        review_note="",
                        status="RETURNED",
                        idempotency_key=idempotency_key,
                        request_hash=request_hash,
                        created_at=now,
                    )
                )
                session.add(
                    BusinessTaskRow(
                        task_id=task_id,
                        task_type="CORRECTION_REFILL",
                        resource_id=correction_id,
                        factory_id=factory_id,
                        assigned_to=assigned_to,
                        status="PENDING",
                        payload={"submission_id": submission_id, "reason": reason.strip()},
                        created_at=now,
                    )
                )
                projection.status = "HELD"
                projection.updated_at = now
                self._event(
                    session,
                    "FINANCE_HELD",
                    submission_id,
                    projection.root_submission_id,
                    factory_id,
                    requested_by,
                    {"correction_id": correction_id, "reason": reason.strip()},
                    now,
                    projection.business_date,
                )
                session.flush()
            except IntegrityError:
                session.rollback()
                # Race: another transaction created the same (requested_by, idempotency_key)
                # Re-read and decide
                with Session(self._engine) as retry_session:
                    race_existing = retry_session.scalar(
                        select(SubmissionCorrectionRow).where(
                            SubmissionCorrectionRow.requested_by == requested_by,
                            SubmissionCorrectionRow.idempotency_key == idempotency_key,
                        )
                    )
                    if race_existing is None:
                        raise  # should not happen — unique constraint triggered but row missing
                    if request_hash and race_existing.request_hash != request_hash:
                        raise SubmissionLedgerError(
                            "IDEMPOTENCY_CONFLICT",
                            "并发冲突：同一幂等键对应不同更正请求。",
                        ) from None
                    return {
                        "correction_id": race_existing.correction_id,
                        "task_id": "",
                        "status": race_existing.status,
                    }
        return {"correction_id": correction_id, "task_id": task_id, "status": "RETURNED"}

    def attach_replacement(
        self,
        correction_id: str,
        *,
        replacement_submission_id: str,
        actual_actor_id: str,
        delegate_reason: str = "",
    ) -> dict[str, str]:
        now = self._clock()
        with Session(self._engine) as session, session.begin():
            correction = session.get(SubmissionCorrectionRow, correction_id)
            if correction is None:
                raise SubmissionLedgerError("CORRECTION_NOT_FOUND", "更正记录不存在。")
            if correction.status != "RETURNED":
                raise SubmissionLedgerError("CORRECTION_STATE_INVALID", "更正当前不可替换。")
            replacement = session.get(
                FinanceEffectiveRecordRow, replacement_submission_id
            )
            root = session.get(FinanceEffectiveRecordRow, correction.root_submission_id)
            if replacement is None or root is None:
                raise SubmissionLedgerError("REPLACEMENT_NOT_FOUND", "替代提交不存在。")
            if replacement.factory_id != correction.factory_id:
                raise SubmissionLedgerError("CROSS_FACTORY_FORBIDDEN", "替代提交必须属于同厂。")
            if (
                actual_actor_id != correction.original_actor_id
                and not delegate_reason.strip()
            ):
                raise SubmissionLedgerError("DELEGATE_REASON_REQUIRED", "代填必须填写原因。")
            correction.replacement_submission_id = replacement_submission_id
            correction.actual_actor_id = actual_actor_id
            correction.delegate_reason = delegate_reason.strip()
            correction.status = "REPLACED"
            correction.replaced_at = now
            session.delete(replacement)
            session.flush()
            root.effective_submission_id = replacement_submission_id
            root.subject_employee_code = replacement.subject_employee_code
            root.definition_version_id = replacement.definition_version_id
            root.values = replacement.values
            root.submitted_at = replacement.submitted_at
            root.status = "PENDING_REVIEW"
            root.updated_at = now
            task = session.scalar(
                select(BusinessTaskRow).where(
                    BusinessTaskRow.resource_id == correction_id,
                    BusinessTaskRow.status == "PENDING",
                )
            )
            if task is not None:
                task.status = "COMPLETED"
                task.completed_at = now
            session.add(
                BusinessTaskRow(
                    task_id=self._id("BT"),
                    task_type="CORRECTION_REVIEW",
                    resource_id=correction_id,
                    factory_id=correction.factory_id,
                    assigned_to="FINANCE",
                    status="PENDING",
                    payload={"replacement_submission_id": replacement_submission_id},
                    created_at=now,
                )
            )
            self._event(
                session,
                "CORRECTION_APPENDED",
                replacement_submission_id,
                root.root_submission_id,
                root.factory_id,
                actual_actor_id,
                {
                    "correction_id": correction_id,
                    "replacement_submission_id": replacement_submission_id,
                    "replacement": self._projection_payload(root),
                },
                now,
                root.business_date,
            )
        return {"correction_id": correction_id, "status": "REPLACED"}

    def review_correction(
        self,
        correction_id: str,
        *,
        approved: bool,
        reviewer_id: str,
        note: str,
    ) -> dict[str, str]:
        now = self._clock()
        with Session(self._engine) as session, session.begin():
            correction = session.get(SubmissionCorrectionRow, correction_id)
            if correction is None or correction.status != "REPLACED":
                raise SubmissionLedgerError("CORRECTION_STATE_INVALID", "更正尚不可审核。")
            projection = session.get(
                FinanceEffectiveRecordRow, correction.root_submission_id
            )
            if projection is None:
                raise SubmissionLedgerError("PROJECTION_NOT_FOUND", "有效记录缺失。")
            correction.status = "APPROVED" if approved else "REJECTED"
            correction.reviewed_by = reviewer_id
            correction.review_note = note.strip()
            correction.reviewed_at = now
            projection.status = "ACTIVE" if approved else "HELD"
            projection.updated_at = now
            task = session.scalar(
                select(BusinessTaskRow).where(
                    BusinessTaskRow.resource_id == correction_id,
                    BusinessTaskRow.task_type == "CORRECTION_REVIEW",
                    BusinessTaskRow.status == "PENDING",
                )
            )
            if task is not None:
                task.status = "COMPLETED"
                task.completed_at = now
            self._event(
                session,
                "FINANCE_APPROVED" if approved else "FINANCE_REJECTED",
                projection.effective_submission_id,
                projection.root_submission_id,
                projection.factory_id,
                reviewer_id,
                {"correction_id": correction_id, "note": note.strip()},
                now,
                projection.business_date,
            )
            result_status = correction.status
        return {"correction_id": correction_id, "status": result_status}

    def get_effective(self, submission_id: str) -> dict[str, object]:
        with Session(self._engine) as session:
            row = session.get(FinanceEffectiveRecordRow, submission_id)
            if row is None:
                raise SubmissionLedgerError("SUBMISSION_NOT_FOUND", "未找到当前有效提交。")
            return self._projection_payload(row)

    def overview(self, factory_id: str | None = None, scope: str | None = None) -> dict[str, int]:
        today = self.business_date(self._clock())
        month = today[:7]
        year = today[:4]
        with Session(self._engine) as session:
            filters = [FinanceEffectiveRecordRow.status == "ACTIVE"]
            if factory_id:
                filters.append(FinanceEffectiveRecordRow.factory_id == factory_id)
            if scope == "today":
                filters.append(FinanceEffectiveRecordRow.business_date == today)
            elif scope == "month":
                filters.append(FinanceEffectiveRecordRow.business_date.like(f"{month}%"))
            elif scope == "year":
                filters.append(FinanceEffectiveRecordRow.business_date.like(f"{year}%"))
            def count(prefix: str) -> int:
                return int(
                    session.scalar(
                        select(func.count())
                        .select_from(FinanceEffectiveRecordRow)
                        .where(*filters, FinanceEffectiveRecordRow.business_date.like(f"{prefix}%"))
                    )
                    or 0
                )
            return {"today": count(today), "month": count(month), "year": count(year)}

    def list_ledger(
        self, factory_id: str | None = None, scope: str | None = None
    ) -> dict[str, object]:
        with Session(self._engine) as session:
            statement = select(FinanceEffectiveRecordRow).order_by(
                FinanceEffectiveRecordRow.submitted_at.desc()
            )
            if factory_id:
                statement = statement.where(
                    FinanceEffectiveRecordRow.factory_id == factory_id
                )
            if scope == "today":
                statement = statement.where(
                    FinanceEffectiveRecordRow.business_date == self.business_date(self._clock())
                )
            elif scope == "month":
                month = self.business_date(self._clock())[:7]
                statement = statement.where(
                    FinanceEffectiveRecordRow.business_date.like(f"{month}%")
                )
            elif scope == "year":
                year = self.business_date(self._clock())[:4]
                statement = statement.where(
                    FinanceEffectiveRecordRow.business_date.like(f"{year}%")
                )
            items = session.scalars(statement).all()
            return {"items": [self._projection_payload(row) for row in items]}

    def watermark(self) -> str:
        with Session(self._engine) as session:
            value = session.scalar(select(func.max(FinanceLedgerEventRow.occurred_at)))
            return value.isoformat() if value is not None else self._clock().isoformat()

    def list_tasks(self, factory_id: str | None = None) -> dict[str, object]:
        with Session(self._engine) as session:
            statement = select(BusinessTaskRow).order_by(BusinessTaskRow.created_at.desc())
            if factory_id:
                statement = statement.where(BusinessTaskRow.factory_id == factory_id)
            rows = session.scalars(statement).all()
            return {
                "items": [
                    {
                        "task_id": row.task_id,
                        "task_type": row.task_type,
                        "resource_id": row.resource_id,
                        "factory_id": row.factory_id,
                        "assigned_to": row.assigned_to,
                        "status": row.status,
                        "payload": row.payload,
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in rows
                ]
            }

    def list_corrections(self, factory_id: str | None = None) -> dict[str, object]:
        with Session(self._engine) as session:
            statement = select(SubmissionCorrectionRow).order_by(
                SubmissionCorrectionRow.created_at.desc()
            )
            if factory_id:
                statement = statement.where(
                    SubmissionCorrectionRow.factory_id == factory_id
                )
            rows = session.scalars(statement).all()
            return {
                "items": [
                    {
                        "correction_id": row.correction_id,
                        "root_submission_id": row.root_submission_id,
                        "original_submission_id": row.original_submission_id,
                        "replacement_submission_id": row.replacement_submission_id,
                        "factory_id": row.factory_id,
                        "reason": row.reason,
                        "delegate_reason": row.delegate_reason,
                        "original_actor_id": row.original_actor_id,
                        "actual_actor_id": row.actual_actor_id,
                        "requested_by": row.requested_by,
                        "reviewed_by": row.reviewed_by,
                        "review_note": row.review_note,
                        "status": row.status,
                        "idempotency_key": row.idempotency_key or "",
                        "request_hash": row.request_hash or "",
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in rows
                ]
            }

    def rebuild_projection(self) -> int:
        with Session(self._engine) as session, session.begin():
            session.execute(delete(FinanceEffectiveRecordRow))
            events = session.scalars(
                select(FinanceLedgerEventRow).order_by(
                    FinanceLedgerEventRow.occurred_at, FinanceLedgerEventRow.event_id
                )
            ).all()
            for event in events:
                if event.event_type == "SUBMISSION_ACCEPTED":
                    payload = event.payload
                    submitted_at = datetime.fromisoformat(str(payload["submitted_at"]))
                    session.merge(
                        FinanceEffectiveRecordRow(
                            root_submission_id=event.root_submission_id,
                            effective_submission_id=event.submission_id,
                            factory_id=event.factory_id,
                            subject_employee_code=str(payload["subject_employee_code"]),
                            definition_version_id=str(payload["definition_version_id"]),
                            business_date=event.business_date,
                            submitted_at=submitted_at,
                            values=dict(payload["values"]),
                            status="ACTIVE",
                            updated_at=event.occurred_at,
                        )
                    )
                elif event.event_type == "CORRECTION_APPENDED":
                    replacement = dict(event.payload["replacement"])
                    old = session.get(
                        FinanceEffectiveRecordRow, event.submission_id
                    )
                    if old is not None and old.root_submission_id != event.root_submission_id:
                        session.delete(old)
                        session.flush()
                    root = session.get(
                        FinanceEffectiveRecordRow, event.root_submission_id
                    )
                    if root is not None:
                        root.effective_submission_id = event.submission_id
                        root.subject_employee_code = str(
                            replacement["subject_employee_code"]
                        )
                        root.definition_version_id = str(
                            replacement["definition_version_id"]
                        )
                        root.values = dict(replacement["values"])
                        root.status = "PENDING_REVIEW"
                elif event.event_type in {"FINANCE_APPROVED", "FINANCE_REJECTED"}:
                    row = session.get(
                        FinanceEffectiveRecordRow, event.root_submission_id
                    )
                    if row is not None:
                        row.status = (
                            "ACTIVE"
                            if event.event_type == "FINANCE_APPROVED"
                            else "HELD"
                        )
            return int(
                session.scalar(
                    select(func.count()).select_from(FinanceEffectiveRecordRow)
                )
                or 0
            )

    @staticmethod
    def _projection_payload(row: FinanceEffectiveRecordRow) -> dict[str, object]:
        return {
            "root_submission_id": row.root_submission_id,
            "effective_submission_id": row.effective_submission_id,
            "factory_id": row.factory_id,
            "subject_employee_code": row.subject_employee_code,
            "definition_version_id": row.definition_version_id,
            "business_date": row.business_date,
            "submitted_at": row.submitted_at.isoformat(),
            "values": row.values,
            "status": row.status,
        }

    @staticmethod
    def _id(prefix: str) -> str:
        return f"{prefix}-{uuid4().hex[:16].upper()}"

    def _event(
        self,
        session: Session,
        event_type: str,
        submission_id: str,
        root_submission_id: str,
        factory_id: str,
        actor_id: str,
        payload: dict[str, Any],
        occurred_at: datetime,
        business_date: str,
    ) -> None:
        session.add(
            FinanceLedgerEventRow(
                event_id=self._id("FLE"),
                event_type=event_type,
                submission_id=submission_id,
                root_submission_id=root_submission_id,
                factory_id=factory_id,
                business_date=business_date,
                payload=payload,
                actor_id=actor_id,
                occurred_at=occurred_at,
            )
        )
