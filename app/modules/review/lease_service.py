"""Time-bounded exclusive review leases."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Protocol
from uuid import uuid4

from app.domain.models import AuditEvent
from app.modules.review.models import LeaseHeldError, LeaseOwnershipError, ReviewLease
from app.modules.review.repository import SqlAlchemyReviewLeaseRepository


class LeaseAuditWriter(Protocol):
    def add_audit_event(self, event: AuditEvent) -> None: ...


class ReviewLeaseService:
    def __init__(
        self,
        repository: SqlAlchemyReviewLeaseRepository,
        *,
        clock: Callable[[], datetime] | None = None,
        ttl_seconds: int = 300,
        audits: LeaseAuditWriter | None = None,
    ) -> None:
        self._repository = repository
        self._clock = clock or (lambda: datetime.now(UTC))
        self._ttl = timedelta(seconds=ttl_seconds)
        self._audits = audits

    def acquire(self, form_id: str, owner_id: str) -> ReviewLease:
        now = self._clock()
        existing = self._repository.get(form_id)
        if existing is not None and existing.expires_at > now:
            raise LeaseHeldError(f"Form {form_id} is held by {existing.owner_id}")
        if existing is not None:
            self._repository.delete(form_id)
        lease = ReviewLease(
            form_id=form_id,
            owner_id=owner_id,
            lease_token=uuid4().hex,
            acquired_at=now,
            expires_at=now + self._ttl,
            heartbeat_at=now,
        )
        self._repository.save(lease)
        self._audit(form_id, "LEASE_ACQUIRE", owner_id, now)
        return lease

    def heartbeat(self, form_id: str, owner_id: str, lease_token: str) -> ReviewLease:
        lease = self._require_owned(form_id, owner_id, lease_token)
        now = self._clock()
        renewed = ReviewLease(
            form_id=lease.form_id,
            owner_id=lease.owner_id,
            lease_token=lease.lease_token,
            acquired_at=lease.acquired_at,
            expires_at=now + self._ttl,
            heartbeat_at=now,
        )
        self._repository.save(renewed)
        self._audit(form_id, "LEASE_HEARTBEAT", owner_id, now)
        return renewed

    def release(self, form_id: str, owner_id: str, lease_token: str) -> None:
        self._require_owned(form_id, owner_id, lease_token)
        self._repository.delete(form_id)
        self._audit(form_id, "LEASE_RELEASE", owner_id, self._clock())

    def force_release(self, form_id: str, actor_id: str, reason: str) -> None:
        if not reason.strip():
            raise ValueError("A force-release reason is required")
        if self._repository.get(form_id) is not None:
            self._repository.delete(form_id)
            self._audit(form_id, "LEASE_FORCE_RELEASE", actor_id, self._clock(), reason)

    def assert_owned(self, form_id: str, owner_id: str, lease_token: str) -> ReviewLease:
        return self._require_owned(form_id, owner_id, lease_token)

    def _require_owned(self, form_id: str, owner_id: str, lease_token: str) -> ReviewLease:
        lease = self._repository.get(form_id)
        now = self._clock()
        if (
            lease is None
            or lease.expires_at <= now
            or lease.owner_id != owner_id
            or lease.lease_token != lease_token
        ):
            raise LeaseOwnershipError(
                f"Actor {owner_id} does not hold an active lease for {form_id}"
            )
        return lease

    def _audit(
        self,
        form_id: str,
        event_type: str,
        actor_id: str,
        timestamp: datetime,
        reason: str | None = None,
    ) -> None:
        if self._audits is not None:
            self._audits.add_audit_event(
                AuditEvent(
                    event_id=f"EVENT-{uuid4().hex}",
                    form_id=form_id,
                    event_type=event_type,
                    actor_id=actor_id,
                    timestamp=timestamp,
                    reason=reason,
                    evidence_ids=(),
                )
            )


__all__ = ["LeaseHeldError", "LeaseOwnershipError", "ReviewLeaseService"]
