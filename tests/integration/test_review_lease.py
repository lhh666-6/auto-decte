from datetime import UTC, datetime, timedelta

import pytest

from app.adapters.database.models import Base
from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.adapters.storage.local import LocalEvidenceStorage
from app.application.import_forms import ImportForms
from app.infrastructure.database.sqlite import create_sqlite_engine
from app.infrastructure.database.uow import SqlAlchemyUnitOfWork
from app.modules.review.facade import ConfirmReviewCommand, ReviewFacade
from app.modules.review.lease_service import LeaseHeldError, ReviewLeaseService
from app.modules.review.models import ReviewVersionConflict
from app.modules.review.repository import SqlAlchemyReviewLeaseRepository


class FrozenClock:
    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


def test_second_reviewer_cannot_acquire_live_lease(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "demo.db")
    Base.metadata.create_all(engine)
    clock = FrozenClock(datetime(2026, 7, 12, tzinfo=UTC))
    leases = ReviewLeaseService(
        SqlAlchemyReviewLeaseRepository(engine), clock=clock, ttl_seconds=60
    )

    first = leases.acquire("FORM-1", "reviewer-a")

    with pytest.raises(LeaseHeldError):
        leases.acquire("FORM-1", "reviewer-b")
    assert first.owner_id == "reviewer-a"


def test_expired_lease_can_be_reacquired_and_owner_can_heartbeat(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "demo.db")
    Base.metadata.create_all(engine)
    clock = FrozenClock(datetime(2026, 7, 12, tzinfo=UTC))
    leases = ReviewLeaseService(
        SqlAlchemyReviewLeaseRepository(engine), clock=clock, ttl_seconds=60
    )
    first = leases.acquire("FORM-1", "reviewer-a")
    clock.advance(30)

    renewed = leases.heartbeat("FORM-1", "reviewer-a", first.lease_token)
    assert renewed.expires_at == clock.now + timedelta(seconds=60)
    clock.advance(61)

    second = leases.acquire("FORM-1", "reviewer-b")
    assert second.owner_id == "reviewer-b"


def test_force_release_requires_reason_and_removes_lease(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "demo.db")
    Base.metadata.create_all(engine)
    leases = ReviewLeaseService(SqlAlchemyReviewLeaseRepository(engine))
    leases.acquire("FORM-1", "reviewer-a")

    with pytest.raises(ValueError, match="reason"):
        leases.force_release("FORM-1", "admin-a", "")
    leases.force_release("FORM-1", "admin-a", "reviewer left shift")

    assert SqlAlchemyReviewLeaseRepository(engine).get("FORM-1") is None


def test_lease_operations_append_audit_events_when_configured(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "demo.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    ImportForms(
        repository, repository, repository, LocalEvidenceStorage(tmp_path / "evidence")
    ).import_image(image, "FORM-1", "T1", "1", "operator-a")
    leases = ReviewLeaseService(SqlAlchemyReviewLeaseRepository(engine), audits=repository)

    lease = leases.acquire("FORM-1", "reviewer-a")
    leases.heartbeat("FORM-1", "reviewer-a", lease.lease_token)
    leases.force_release("FORM-1", "admin-a", "shift handover")

    assert [event.event_type for event in repository.list_audit_events("FORM-1")][-3:] == [
        "LEASE_ACQUIRE",
        "LEASE_HEARTBEAT",
        "LEASE_FORCE_RELEASE",
    ]


def test_confirm_rejects_stale_version_with_conflict_context(tmp_path) -> None:
    engine = create_sqlite_engine(tmp_path / "demo.db")
    Base.metadata.create_all(engine)
    repository = SqlAlchemyFormRepository(engine)
    image = tmp_path / "scan.png"
    image.write_bytes(b"image")
    ImportForms(
        repository, repository, repository, LocalEvidenceStorage(tmp_path / "evidence")
    ).import_image(image, "FORM-1", "T1", "1", "operator-a")
    leases = ReviewLeaseService(SqlAlchemyReviewLeaseRepository(engine))
    lease = leases.acquire("FORM-1", "reviewer-a")
    facade = ReviewFacade(
        uow_factory=lambda: SqlAlchemyUnitOfWork(engine),
        leases=leases,
    )
    command = ConfirmReviewCommand(
        form_id="FORM-1",
        expected_version=0,
        values={"total_quantity": 10},
        actor_id="reviewer-a",
        reason="initial confirmation",
        evidence_ids=(),
        lease_token=lease.lease_token,
    )
    facade.confirm(command)

    with pytest.raises(ReviewVersionConflict) as error:
        facade.confirm(command)
    assert error.value.submitted_version == 0
    assert error.value.current_version == 1
