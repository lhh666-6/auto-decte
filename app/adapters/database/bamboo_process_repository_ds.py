"""SQLAlchemy persistence for the bamboo production workflow."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Engine, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooCageOccupancyRow,
    BambooCorrectionCaseRow,
    BambooDailyExportBatchRow,
    BambooDailyExportItemRow,
    BambooInspectionExceptionRow,
    BambooInspectionWindowRow,
    BambooPayrollFactRow,
    BambooPayrollRuleVersionRow,
    BambooPlantAuditRow,
    BambooRecordRow,
    BambooSignatureRow,
    BambooStageSubmissionRow,
)
from app.modules.bamboo_process.errors_ds import (
    BambooIdempotencyConflict,
    BambooPermissionDenied,
    StaleBambooRevision,
)
from app.modules.bamboo_process.models_ds import (
    BambooFormType,
    BambooRecord,
    BambooRecordStatus,
    BambooStage,
    ElectronicSignature,
    StageSubmission,
)
from app.modules.bamboo_process.ports_ds import (
    BambooCageOccupied,
    BambooRepositoryConflict,
)

DEFAULT_BAMBOO_PAYROLL_RULES: tuple[tuple[str, str, dict[str, object]], ...] = (
    (
        "system-sort-v1",
        "SORT",
        {"unit_rate": "1.00", "length_multipliers": {"2.1": "5", "2.3": "6", "2.5": "7"}},
    ),
    (
        "system-joint-v1",
        "DIPPING_DRYING_JOINT",
        {"dipping_rate": "1.00", "drying_rate": "1.00"},
    ),
)


def install_default_bamboo_payroll_rules(engine: Engine) -> None:
    now = datetime.now(UTC)
    with Session(engine) as session, session.begin():
        for rule_version_id, rule_key, configuration in DEFAULT_BAMBOO_PAYROLL_RULES:
            if session.get(BambooPayrollRuleVersionRow, rule_version_id) is None:
                session.add(
                    BambooPayrollRuleVersionRow(
                        rule_version_id=rule_version_id,
                        rule_key=rule_key,
                        factory_id=None,
                        version=1,
                        configuration=configuration,
                        active=True,
                        effective_at=now,
                        created_by="SYSTEM",
                        created_at=now,
                    )
                )


class SqlAlchemyBambooProcessRepository:
    def __init__(self, engine: Engine, *, plant_audit_wait_hours: float = 0.0) -> None:
        self._engine = engine
        self._plant_audit_wait_hours = plant_audit_wait_hours
        install_default_bamboo_payroll_rules(engine)

    def next_display_sequence(self, factory_id: str, production_date: str) -> int:
        # Display numbers are externally visible and globally unique. Factory access
        # remains scoped by factory_id, but the daily sequence spans all factories.
        del factory_id
        date_token = production_date.replace("-", "")
        with Session(self._engine) as session:
            display_numbers = session.scalars(
                select(BambooRecordRow.display_no)
                .where(
                    BambooRecordRow.display_no.like(f"ZS-{date_token}-%"),
                )
            ).all()
        sequences: list[int] = []
        for display_no in display_numbers:
            try:
                sequences.append(int(display_no.rsplit("-", 1)[-1]))
            except ValueError:
                continue
        return max(sequences, default=0) + 1

    def add(self, record: BambooRecord) -> BambooRecord:
        try:
            with Session(self._engine) as session, session.begin():
                session.add(_record_row(record))
        except IntegrityError as error:
            if record.source_type == "MOBILE_CREATED" and record.source_ref:
                existing = self.find_created_result(
                    record.created_by,
                    record.source_ref,
                    payload_hash=record.create_payload_hash,
                )
                if existing is not None:
                    return existing
            if record.source_record_id is not None:
                linked = self.find_linked(
                    record.form_type,
                    record.source_record_id,
                )
                if linked is not None:
                    return linked
            raise BambooRepositoryConflict(
                "bamboo record persistence conflict; retry with the same idempotency key"
            ) from error
        stored = self.get(record.record_id)
        if stored is None:  # pragma: no cover - guarded by the successful insert
            raise RuntimeError("bamboo record disappeared after insert")
        return stored

    def add_sorting_with_cage_occupancy(
        self,
        record: BambooRecord,
        cage_no: str,
    ) -> BambooRecord:
        cage_no = cage_no.strip()
        cage_no_key = cage_no.casefold()
        try:
            with Session(self._engine) as session, session.begin():
                session.add(_record_row(record))
                session.flush()
                session.add(
                    BambooCageOccupancyRow(
                        occupancy_id=str(uuid4()),
                        factory_id=record.factory_id,
                        cage_no=cage_no,
                        cage_no_key=cage_no_key,
                        sorting_record_id=record.record_id,
                        acquired_at=record.created_at,
                        released_at=None,
                        released_by_submission_id=None,
                    )
                )
                session.flush()
        except IntegrityError as error:
            if record.source_type == "MOBILE_CREATED" and record.source_ref:
                repeated = self.find_created_result(
                    record.created_by,
                    record.source_ref,
                    payload_hash=record.create_payload_hash,
                )
                if repeated is not None:
                    return repeated
            active = self._active_cage_occupancy(record.factory_id, cage_no_key)
            if active is not None:
                raise BambooCageOccupied(
                    active.cage_no,
                    active.sorting_record_id,
                ) from error
            raise BambooRepositoryConflict(
                "bamboo sorting persistence conflict; retry with the same idempotency key"
            ) from error
        stored = self.get(record.record_id)
        if stored is None:  # pragma: no cover - guarded by the successful insert
            raise RuntimeError("bamboo record disappeared after cage acquisition")
        return stored

    def _active_cage_occupancy(
        self,
        factory_id: str,
        cage_no_key: str,
    ) -> BambooCageOccupancyRow | None:
        with Session(self._engine) as session:
            return session.scalar(
                select(BambooCageOccupancyRow).where(
                    BambooCageOccupancyRow.factory_id == factory_id,
                    BambooCageOccupancyRow.cage_no_key == cage_no_key,
                    BambooCageOccupancyRow.released_at.is_(None),
                )
            )

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

    def list_for_factory(self, factory_id: str) -> list[BambooRecord]:
        with Session(self._engine) as session:
            record_ids = session.scalars(
                select(BambooRecordRow.record_id)
                .where(BambooRecordRow.factory_id == factory_id)
                .order_by(BambooRecordRow.updated_at.desc())
            ).all()
        return [record for record_id in record_ids if (record := self.get(record_id))]

    def list_all(self) -> list[BambooRecord]:
        with Session(self._engine) as session:
            record_ids = session.scalars(
                select(BambooRecordRow.record_id).order_by(BambooRecordRow.updated_at.desc())
            ).all()
        return [record for record_id in record_ids if (record := self.get(record_id))]

    def find_created_result(
        self,
        actor_id: str,
        source_ref: str,
        *,
        payload_hash: str | None = None,
    ) -> BambooRecord | None:
        with Session(self._engine) as session:
            row = session.scalar(
                select(BambooRecordRow).where(
                    BambooRecordRow.created_by == actor_id,
                    BambooRecordRow.source_type == "MOBILE_CREATED",
                    BambooRecordRow.source_ref == source_ref,
                )
            )
        if row is None:
            return None
        if payload_hash is not None:
            if row.create_payload_hash is None:
                # Old record that cannot be verified — reject conservatively
                raise BambooIdempotencyConflict(
                    actor_id, source_ref, "create_record"
                )
            if row.create_payload_hash != payload_hash:
                raise BambooIdempotencyConflict(
                    actor_id, source_ref, "create_record"
                )
        return self.get(row.record_id)

    def find_idempotent_result(
        self,
        actor_id: str,
        idempotency_key: str,
        *,
        idempotency_payload_hash: str | None = None,
        legacy_comparison_hash: str | None = None,
    ) -> BambooRecord | None:
        """Return the record for a previous submission under this key.

        - v1 signatures compare *idempotency_payload_hash* against
          ``idempotency_payload_hash``.
        - v0 signatures compare *legacy_comparison_hash* against the
          stored ``payload_hash`` (the caller must compute it with the
          stored version, not the version the new submission would get).

        Mismatch raises ``BambooIdempotencyConflict``.
        """
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
            # Version >= 1: compare against dedicated idempotency hash
            if signature.idempotency_hash_version >= 1:
                if (
                    idempotency_payload_hash is not None
                    and signature.idempotency_payload_hash
                    != idempotency_payload_hash
                ):
                    raise BambooIdempotencyConflict(
                        actor_id, idempotency_key, "submit_stage"
                    )
            # Legacy (version 0): compare caller-supplied hash vs stored
            elif legacy_comparison_hash is not None:
                if signature.payload_hash != legacy_comparison_hash:
                    raise BambooIdempotencyConflict(
                        actor_id, idempotency_key, "submit_stage"
                    )
            # Legacy with no comparison hash → reject
            elif idempotency_payload_hash is not None:
                raise BambooIdempotencyConflict(
                    actor_id, idempotency_key, "submit_stage"
                )
            record_id = submission.record_id if submission is not None else None
        return self.get(record_id) if record_id is not None else None

    def find_linked(
        self,
        form_type: BambooFormType,
        source_record_id: str,
    ) -> BambooRecord | None:
        with Session(self._engine) as session:
            record_id = session.scalar(
                select(BambooRecordRow.record_id).where(
                    BambooRecordRow.form_type == form_type.value,
                    BambooRecordRow.source_record_id == source_record_id,
                )
            )
        return self.get(record_id) if record_id is not None else None

    def append_stage(
        self,
        *,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
        expected_revision: int,
        linked_record: BambooRecord | None = None,
    ) -> BambooRecord:
        try:
            return self._append_stage_once(
                record=record,
                submission=submission,
                signature=signature,
                expected_revision=expected_revision,
                linked_record=linked_record,
            )
        except IntegrityError as error:
            repeated = self.find_idempotent_result(
                signature.actor_id,
                signature.idempotency_key,
                idempotency_payload_hash=signature.idempotency_payload_hash,
                legacy_comparison_hash=(
                    signature.payload_hash
                    if signature.idempotency_hash_version == 0
                    else None
                ),
            )
            if repeated is not None:
                return repeated
            raise BambooRepositoryConflict(
                "bamboo stage persistence conflict; retry with the same idempotency key"
            ) from error

    def _append_stage_once(
        self,
        *,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
        expected_revision: int,
        linked_record: BambooRecord | None,
    ) -> BambooRecord:
        with Session(self._engine) as session, session.begin():
            self._validate_stage_gate(session, submission)
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
                            record.current_stage.value if record.current_stage is not None else None
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
            session.flush()
            self._apply_stage_side_effects(session, record, submission, signature)
            if linked_record is not None:
                existing_link = session.scalar(
                    select(BambooRecordRow.record_id).where(
                        BambooRecordRow.form_type == linked_record.form_type.value,
                        BambooRecordRow.source_record_id
                        == linked_record.source_record_id,
                    )
                )
                if existing_link is None:
                    session.add(_record_row(linked_record))
        stored = self.get(record.record_id)
        if stored is None:  # pragma: no cover - guarded by the successful update
            raise RuntimeError("bamboo record disappeared after stage submission")
        return stored

    def _validate_stage_gate(self, session: Session, submission: StageSubmission) -> None:
        if submission.stage is BambooStage.SUPERVISOR:
            open_count = session.scalar(
                select(func.count())
                .select_from(BambooInspectionExceptionRow)
                .where(
                    BambooInspectionExceptionRow.record_id == submission.record_id,
                    BambooInspectionExceptionRow.status == "OPEN",
                )
            )
            if int(open_count or 0):
                raise BambooPermissionDenied("open inspection exceptions must be closed")
        if submission.stage is BambooStage.PLANT_AUDIT:
            open_count = session.scalar(
                select(func.count())
                .select_from(BambooInspectionExceptionRow)
                .where(
                    BambooInspectionExceptionRow.record_id == submission.record_id,
                    BambooInspectionExceptionRow.status == "OPEN",
                )
            )
            if int(open_count or 0):
                raise BambooPermissionDenied("open inspection exceptions must be closed")
            supervisor_at = session.scalar(
                select(BambooStageSubmissionRow.submitted_at)
                .where(
                    BambooStageSubmissionRow.record_id == submission.record_id,
                    BambooStageSubmissionRow.stage_key == BambooStage.SUPERVISOR.value,
                    BambooStageSubmissionRow.invalidated.is_(False),
                )
                .order_by(BambooStageSubmissionRow.version.desc())
            )
            if supervisor_at is None:
                raise BambooPermissionDenied("supervisor signature is required")
            window = session.get(BambooInspectionWindowRow, submission.record_id)
            if window is not None:
                submitted_at = submission.submitted_at
                if submitted_at is None:
                    raise BambooPermissionDenied("厂长签字缺少服务器时间")
                if window.status in {"OPEN", "CLAIMED"}:
                    if submitted_at < _utc(window.deadline_at):
                        raise BambooPermissionDenied(
                            f"检测窗口将在 {_utc(window.deadline_at).isoformat()} 后结束"
                        )
                    window.status = "EXPIRED"
                    window.appeal_deadline_at = _utc(window.deadline_at) + timedelta(hours=24)
                    window.revision += 1
                if window.status not in {
                    "COMPLETED",
                    "EARLY_TERMINATED",
                    "EXPIRED",
                    "APPEAL_CLAIMED",
                    "APPEAL_REJECTED",
                }:
                    raise BambooPermissionDenied("当前检测或申诉尚未结束")
            elif self._plant_audit_wait_hours > 0:
                earliest = _utc(supervisor_at) + timedelta(
                    hours=self._plant_audit_wait_hours
                )
                submitted_at = submission.submitted_at
                if submitted_at is None or submitted_at < earliest:
                    raise BambooPermissionDenied(
                        f"厂长审核将在 {earliest.isoformat()} 后开放"
                    )

    def _apply_stage_side_effects(
        self,
        session: Session,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
    ) -> None:
        if (
            record.form_type is BambooFormType.SORTING
            and submission.stage is BambooStage.SORT
        ):
            self._create_sort_fact(session, record, submission, signature)
        elif (
            record.form_type is BambooFormType.DIPPING_DRYING
            and submission.stage is BambooStage.DRYING
        ):
            self._create_joint_fact(session, record, submission, signature)
        elif submission.stage is BambooStage.PLANT_AUDIT:
            self._activate_payroll_and_export(session, record, submission, signature)
        # Create inspection window when the last production stage is submitted
        # (SORT for SORTING, DRYING for DIPPING_DRYING). Inspectors can then work
        # in parallel with the supervisor instead of waiting for supervisor sign-off.
        # SUPERVISOR submission is kept as a fallback for records created before
        # this change shipped.
        is_last_production = (
            (record.form_type is BambooFormType.SORTING
             and submission.stage is BambooStage.SORT)
            or (record.form_type is BambooFormType.DIPPING_DRYING
                and submission.stage is BambooStage.DRYING)
        )
        if is_last_production or submission.stage is BambooStage.SUPERVISOR:
            window = session.get(BambooInspectionWindowRow, record.record_id)
            if window is None:
                opened_at = submission.submitted_at
                if opened_at is None:  # pragma: no cover - signed submissions have server time
                    raise RuntimeError("submission is missing server time")
                session.add(
                    BambooInspectionWindowRow(
                        record_id=record.record_id,
                        factory_id=record.factory_id,
                        opened_at=opened_at,
                        deadline_at=opened_at + timedelta(hours=2),
                        status="OPEN",
                        claimed_by=None,
                        claimed_at=None,
                        inspection_id=None,
                        completed_at=None,
                        terminated_by=None,
                        terminated_at=None,
                        appeal_deadline_at=None,
                        appeal_claimed_by=None,
                        appeal_claimed_at=None,
                        appeal_payload=None,
                        appeal_submitted_at=None,
                        appeal_decision=None,
                        appeal_decision_note=None,
                        appeal_decided_by=None,
                        appeal_decided_at=None,
                        revision=1,
                    )
                )
        if (
            record.form_type is BambooFormType.DIPPING_DRYING
            and submission.stage is BambooStage.SUPERVISOR
            and record.production_object_id
        ):
            session.execute(
                update(BambooCageOccupancyRow)
                .where(
                    BambooCageOccupancyRow.sorting_record_id
                    == record.production_object_id,
                    BambooCageOccupancyRow.released_at.is_(None),
                )
                .values(
                    released_at=submission.submitted_at,
                    released_by_submission_id=submission.submission_id,
                )
            )

    def _rule(
        self,
        session: Session,
        rule_key: str,
        factory_id: str,
    ) -> BambooPayrollRuleVersionRow:
        for scoped_factory in (factory_id, None):
            row = session.scalar(
                select(BambooPayrollRuleVersionRow)
                .where(
                    BambooPayrollRuleVersionRow.rule_key == rule_key,
                    BambooPayrollRuleVersionRow.factory_id == scoped_factory,
                    BambooPayrollRuleVersionRow.active.is_(True),
                )
                .order_by(
                    BambooPayrollRuleVersionRow.effective_at.desc(),
                    BambooPayrollRuleVersionRow.version.desc(),
                )
            )
            if row is not None:
                return row
        raise RuntimeError(f"active bamboo payroll rule not found: {rule_key}")

    def _next_fact_version(self, session: Session, record_id: str, fact_type: str) -> int:
        current = session.scalar(
            select(func.max(BambooPayrollFactRow.version)).where(
                BambooPayrollFactRow.record_id == record_id,
                BambooPayrollFactRow.fact_type == fact_type,
            )
        )
        return int(current or 0) + 1

    def _create_sort_fact(
        self,
        session: Session,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
    ) -> None:
        rule = self._rule(session, "SORT", record.factory_id)
        quantity = _decimal(
            submission.values.get("sort_quantity", record.base_info.get("bundle_count", 0))
        )
        length = str(submission.values.get("length", record.base_info.get("length", "")))
        multiplier = _decimal(
            dict(rule.configuration.get("length_multipliers", {})).get(length, "1")
        )
        amount = _optional_amount(submission.values.get("wage_amount"))
        if amount is None:
            amount = quantity * multiplier * _decimal(rule.configuration.get("unit_rate", "1"))
        session.add(
            BambooPayrollFactRow(
                fact_id=str(uuid4()),
                record_id=record.record_id,
                fact_type="SORT",
                version=self._next_fact_version(session, record.record_id, "SORT"),
                status="PENDING_EFFECTIVE",
                rule_version_id=rule.rule_version_id,
                input_snapshot={
                    "quantity": str(quantity),
                    "length": length,
                    "multiplier": str(multiplier),
                    "values": submission.values,
                },
                allocations=[
                    {
                        "employee_code": signature.employee_code,
                        "role": signature.role_code,
                        "amount": _money(amount),
                    }
                ],
                total_amount=_money(amount),
                source_submission_ids=[submission.submission_id],
                created_at=signature.signed_at,
            )
        )

    def _create_joint_fact(
        self,
        session: Session,
        record: BambooRecord,
        drying: StageSubmission,
        drying_signature: ElectronicSignature,
    ) -> None:
        dipping = session.scalar(
            select(BambooStageSubmissionRow)
            .where(
                BambooStageSubmissionRow.record_id == record.record_id,
                BambooStageSubmissionRow.stage_key == BambooStage.DIPPING.value,
                BambooStageSubmissionRow.invalidated.is_(False),
            )
            .order_by(BambooStageSubmissionRow.version.desc())
        )
        if dipping is None:
            raise RuntimeError("drying cannot create joint wage without dipping signature")
        dipping_signature = session.scalar(
            select(BambooSignatureRow).where(
                BambooSignatureRow.submission_id == dipping.submission_id
            )
        )
        if dipping_signature is None:
            raise RuntimeError("dipping signature is missing")
        rule = self._rule(session, "DIPPING_DRYING_JOINT", record.factory_id)
        dipping_amount = _optional_amount(dipping.values.get("wage_amount"))
        if dipping_amount is None:
            dipping_amount = _decimal(dipping.values.get("glue_gain", 0)) * _decimal(
                rule.configuration.get("dipping_rate", "1")
            )
        drying_amount = _optional_amount(drying.values.get("wage_amount"))
        if drying_amount is None:
            raw_racks = drying.values.get("rack_numbers")
            rack_numbers = (
                {str(item).strip() for item in raw_racks if str(item).strip()}
                if isinstance(raw_racks, list)
                else set()
            )
            rack_count = len(rack_numbers)
            drying_amount = Decimal(rack_count) * _decimal(
                rule.configuration.get("drying_rate", "1")
            )
        allocations = [
            {
                "employee_code": dipping_signature.employee_code,
                "role": dipping_signature.role_code,
                "amount": _money(dipping_amount),
            },
            {
                "employee_code": drying_signature.employee_code,
                "role": drying_signature.role_code,
                "amount": _money(drying_amount),
            },
        ]
        session.add(
            BambooPayrollFactRow(
                fact_id=str(uuid4()),
                record_id=record.record_id,
                fact_type="DIPPING_DRYING_JOINT",
                version=self._next_fact_version(session, record.record_id, "DIPPING_DRYING_JOINT"),
                status="PENDING_EFFECTIVE",
                rule_version_id=rule.rule_version_id,
                input_snapshot={"dipping": dict(dipping.values), "drying": drying.values},
                allocations=allocations,
                total_amount=_money(dipping_amount + drying_amount),
                source_submission_ids=[dipping.submission_id, drying.submission_id],
                created_at=drying_signature.signed_at,
            )
        )

    def _activate_payroll_and_export(
        self,
        session: Session,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
    ) -> None:
        submitted_at = submission.submitted_at
        if submitted_at is None:  # pragma: no cover - signed submissions always carry server time
            raise RuntimeError("plant audit submission is missing server time")
        session.add(
            BambooPlantAuditRow(
                audit_id=str(uuid4()),
                record_id=record.record_id,
                submission_id=submission.submission_id,
                earliest_at=submitted_at,
                audited_at=submitted_at,
                actor_id=signature.actor_id,
                result="APPROVED",
                revision=record.revision,
            )
        )
        expected_fact_type = (
            "SORT"
            if record.form_type is BambooFormType.SORTING
            else "DIPPING_DRYING_JOINT"
        )
        facts = session.scalars(
            select(BambooPayrollFactRow).where(
                BambooPayrollFactRow.record_id == record.record_id,
                BambooPayrollFactRow.fact_type == expected_fact_type,
                BambooPayrollFactRow.status == "PENDING_EFFECTIVE",
            )
        ).all()
        if not facts:
            return
        business_date = submitted_at.date().isoformat()
        corrections = session.scalars(
            select(BambooCorrectionCaseRow).where(
                BambooCorrectionCaseRow.record_id == record.record_id,
                BambooCorrectionCaseRow.status == "OPEN",
            )
        ).all()
        batch = None
        source_batch_id: str | None = None
        version = 1
        if corrections:
            source_item = session.get(BambooDailyExportItemRow, corrections[0].item_id)
            source_batch_id = source_item.batch_id if source_item is not None else None
            latest_version = session.scalar(
                select(func.max(BambooDailyExportBatchRow.version)).where(
                    BambooDailyExportBatchRow.factory_id == record.factory_id,
                    BambooDailyExportBatchRow.business_date == business_date,
                )
            )
            version = int(latest_version or 0) + 1
        else:
            batch = session.scalar(
                select(BambooDailyExportBatchRow).where(
                    BambooDailyExportBatchRow.factory_id == record.factory_id,
                    BambooDailyExportBatchRow.business_date == business_date,
                    BambooDailyExportBatchRow.version == 1,
                )
            )
        if batch is None:
            batch = BambooDailyExportBatchRow(
                batch_id=str(uuid4()),
                factory_id=record.factory_id,
                business_date=business_date,
                version=version,
                status="OPEN",
                supplemental=bool(corrections),
                source_batch_id=source_batch_id,
                created_by=signature.actor_id,
                created_at=submitted_at,
            )
            session.add(batch)
            session.flush()
        for fact in facts:
            fact.status = "EFFECTIVE"
            fact.effective_at = submitted_at
            for allocation in fact.allocations:
                session.add(
                    BambooDailyExportItemRow(
                        item_id=str(uuid4()),
                        batch_id=batch.batch_id,
                        payroll_fact_id=fact.fact_id,
                        record_id=record.record_id,
                        employee_code=str(allocation["employee_code"]),
                        amount=str(allocation["amount"]),
                        status="PENDING",
                        source_snapshot={
                            "display_no": record.display_no,
                            "fact_type": fact.fact_type,
                            "rule_version_id": fact.rule_version_id,
                            "allocation": allocation,
                        },
                        revision=1,
                    )
                )
        for correction in corrections:
            correction.status = "RESOLVED"
            correction.resolved_at = submitted_at
            correction.supplement_batch_id = batch.batch_id


def _record_row(record: BambooRecord) -> BambooRecordRow:
    return BambooRecordRow(
        record_id=record.record_id,
        display_no=record.display_no,
        factory_id=record.factory_id,
        source_type=record.source_type,
        source_ref=record.source_ref,
        form_type=record.form_type.value,
        production_object_id=record.production_object_id,
        source_record_id=record.source_record_id,
        source_snapshot=record.source_snapshot,
        base_info=record.base_info,
        current_stage=(record.current_stage.value if record.current_stage else None),
        status=record.status.value,
        revision=record.revision,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        create_payload_hash=record.create_payload_hash,
        form_version_id=record.form_version_id,
        form_definition_id=record.form_definition_id,
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
        idempotency_payload_hash=signature.idempotency_payload_hash,
        idempotency_hash_version=signature.idempotency_hash_version,
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
        form_type=BambooFormType(row.form_type),
        production_object_id=row.production_object_id or row.record_id,
        source_record_id=row.source_record_id,
        source_snapshot=dict(row.source_snapshot or {}),
        base_info=dict(row.base_info),
        current_stage=(BambooStage(row.current_stage) if row.current_stage else None),
        status=BambooRecordStatus(row.status),
        revision=row.revision,
        created_by=row.created_by,
        created_at=_utc(row.created_at),
        updated_at=_utc(row.updated_at),
        submissions=tuple(_submission(item) for item in submissions),
        create_payload_hash=row.create_payload_hash,
        form_version_id=row.form_version_id,
        form_definition_id=row.form_definition_id,
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


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except InvalidOperation as error:
        raise ValueError(f"invalid payroll number: {value}") from error


def _optional_amount(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    return _decimal(value)


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))
