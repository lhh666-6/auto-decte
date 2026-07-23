"""Phase 4 immutable finance-ledger and correction-chain acceptance tests."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.adapters.database.models import (
    Base,
    BusinessTaskRow,
    FinanceEffectiveRecordRow,
    FinanceLedgerEventRow,
    SubmissionCorrectionRow,
)
from app.modules.submission_ledger.service_ds import SubmissionLedgerError, SubmissionLedgerService


@pytest.fixture
def ledger(tmp_path):  # type: ignore[no-untyped-def]
    engine = create_engine(f"sqlite:///{(tmp_path / 'ledger.db').as_posix()}")
    Base.metadata.create_all(engine)
    return engine, SubmissionLedgerService(engine)


def _accept(service: SubmissionLedgerService, submission_id: str, when: datetime) -> None:
    service.record_acceptance(
        submission_id=submission_id,
        factory_id="factory-a",
        subject_employee_code="E001",
        actor_id="E001",
        definition_version_id="form-v1",
        values={"quantity": 10},
        submitted_at=when,
    )


def test_acceptance_is_idempotent_and_uses_shanghai_business_date(ledger) -> None:  # type: ignore[no-untyped-def]
    engine, service = ledger
    submitted_at = datetime(2026, 7, 22, 16, 30, tzinfo=UTC)

    _accept(service, "SUB-1", submitted_at)
    _accept(service, "SUB-1", submitted_at)

    with Session(engine) as session:
        events = session.scalars(select(FinanceLedgerEventRow)).all()
        projection = session.get(FinanceEffectiveRecordRow, "SUB-1")
    assert len(events) == 1
    assert projection is not None
    assert projection.business_date == "2026-07-23"
    assert service.overview()["today"] == 1


def test_correction_preserves_original_and_switches_single_effective_record(ledger) -> None:  # type: ignore[no-untyped-def]
    engine, service = ledger
    now = datetime(2026, 7, 23, 1, tzinfo=UTC)
    _accept(service, "SUB-OLD", now)
    _accept(service, "SUB-NEW", now)

    returned = service.return_submission(
        "SUB-OLD",
        factory_id="factory-a",
        reason="数量录入错误",
        requested_by="manager-a",
        assigned_to="E001",
    )
    service.attach_replacement(
        returned["correction_id"],
        replacement_submission_id="SUB-NEW",
        actual_actor_id="leader-a",
        delegate_reason="员工设备故障",
    )
    service.review_correction(
        returned["correction_id"],
        approved=True,
        reviewer_id="finance-a",
        note="复核通过",
    )

    with Session(engine) as session:
        correction = session.get(SubmissionCorrectionRow, returned["correction_id"])
        projections = session.scalars(select(FinanceEffectiveRecordRow)).all()
        tasks = session.scalars(select(BusinessTaskRow)).all()
        event_types = [
            row.event_type
            for row in session.scalars(
                select(FinanceLedgerEventRow).order_by(FinanceLedgerEventRow.occurred_at)
            )
        ]
    assert correction is not None
    assert correction.original_submission_id == "SUB-OLD"
    assert correction.replacement_submission_id == "SUB-NEW"
    assert len(projections) == 1
    assert projections[0].root_submission_id == "SUB-OLD"
    assert projections[0].effective_submission_id == "SUB-NEW"
    assert tasks[0].status == "COMPLETED"
    assert event_types == [
        "SUBMISSION_ACCEPTED",
        "SUBMISSION_ACCEPTED",
        "FINANCE_HELD",
        "CORRECTION_APPENDED",
        "FINANCE_APPROVED",
    ]


def test_cross_factory_return_is_rejected(ledger) -> None:  # type: ignore[no-untyped-def]
    _, service = ledger
    _accept(service, "SUB-1", datetime(2026, 7, 23, tzinfo=UTC))

    with pytest.raises(SubmissionLedgerError, match="CROSS_FACTORY_FORBIDDEN"):
        service.return_submission(
            "SUB-1",
            factory_id="factory-b",
            reason="错误",
            requested_by="manager-b",
            assigned_to="E001",
        )


def test_projection_can_be_rebuilt_from_immutable_events(ledger) -> None:  # type: ignore[no-untyped-def]
    engine, service = ledger
    _accept(service, "SUB-1", datetime(2026, 7, 23, tzinfo=UTC))
    with Session(engine) as session:
        session.query(FinanceEffectiveRecordRow).delete()
        session.commit()

    assert service.rebuild_projection() == 1
    assert service.list_ledger()["items"][0]["effective_submission_id"] == "SUB-1"
