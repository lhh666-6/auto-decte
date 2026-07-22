"""SQLAlchemy persistence for the bamboo production workflow."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Engine, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    BambooCorrectionCaseRow,
    BambooDailyExportBatchRow,
    BambooDailyExportItemRow,
    BambooInspectionExceptionRow,
    BambooPayrollFactRow,
    BambooPayrollRuleVersionRow,
    BambooPlantAuditRow,
    BambooRecordRow,
    BambooSignatureRow,
    BambooStageSubmissionRow,
)
from app.modules.bamboo_process.errors_ds import BambooPermissionDenied, StaleBambooRevision
from app.modules.bamboo_process.models_ds import (
    BambooRecord,
    BambooRecordStatus,
    BambooStage,
    ElectronicSignature,
    StageSubmission,
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
    def __init__(self, engine: Engine, *, plant_audit_wait_hours: float = 12.0) -> None:
        self._engine = engine
        self._plant_audit_wait_hours = plant_audit_wait_hours
        install_default_bamboo_payroll_rules(engine)

    def next_display_sequence(self, factory_id: str, production_date: str) -> int:
        # Display numbers are externally visible and globally unique. Factory access
        # remains scoped by factory_id, but the daily sequence spans all factories.
        del factory_id
        date_token = production_date.replace("-", "")
        with Session(self._engine) as session:
            count = session.scalar(
                select(func.count())
                .select_from(BambooRecordRow)
                .where(
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

    def list_for_factory(self, factory_id: str) -> list[BambooRecord]:
        with Session(self._engine) as session:
            record_ids = session.scalars(
                select(BambooRecordRow.record_id)
                .where(BambooRecordRow.factory_id == factory_id)
                .order_by(BambooRecordRow.updated_at.desc())
            ).all()
        return [record for record_id in record_ids if (record := self.get(record_id))]

    def find_created_result(
        self,
        actor_id: str,
        source_ref: str,
    ) -> BambooRecord | None:
        with Session(self._engine) as session:
            record_id = session.scalar(
                select(BambooRecordRow.record_id).where(
                    BambooRecordRow.created_by == actor_id,
                    BambooRecordRow.source_type == "MOBILE_CREATED",
                    BambooRecordRow.source_ref == source_ref,
                )
            )
        return self.get(record_id) if record_id is not None else None

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
            earliest = _utc(supervisor_at) + timedelta(hours=self._plant_audit_wait_hours)
            submitted_at = submission.submitted_at
            if submitted_at is None or submitted_at < earliest:
                raise BambooPermissionDenied(
                    f"plant audit is available after {earliest.isoformat()}"
                )

    def _apply_stage_side_effects(
        self,
        session: Session,
        record: BambooRecord,
        submission: StageSubmission,
        signature: ElectronicSignature,
    ) -> None:
        if submission.stage is BambooStage.SORT:
            self._create_sort_fact(session, record, submission, signature)
        elif submission.stage is BambooStage.DRYING:
            self._create_joint_fact(session, record, submission, signature)
        elif submission.stage is BambooStage.PLANT_AUDIT:
            self._activate_payroll_and_export(session, record, submission, signature)

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
            drying_amount = _decimal(drying.values.get("rack_count", 0)) * _decimal(
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
        facts = session.scalars(
            select(BambooPayrollFactRow).where(
                BambooPayrollFactRow.record_id == record.record_id,
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
