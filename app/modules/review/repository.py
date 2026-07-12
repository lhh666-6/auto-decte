"""Persistence adapter for review leases."""

from datetime import UTC, datetime

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.adapters.database.models import ReviewLeaseRow
from app.modules.review.models import ReviewLease


class SqlAlchemyReviewLeaseRepository:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, form_id: str) -> ReviewLease | None:
        with Session(self._engine) as session:
            row = session.get(ReviewLeaseRow, form_id)
            return self._to_model(row) if row is not None else None

    def save(self, lease: ReviewLease) -> None:
        with Session(self._engine) as session, session.begin():
            session.merge(
                ReviewLeaseRow(
                    form_id=lease.form_id,
                    owner_id=lease.owner_id,
                    lease_token=lease.lease_token,
                    acquired_at=lease.acquired_at,
                    expires_at=lease.expires_at,
                    heartbeat_at=lease.heartbeat_at,
                    forced_release_by=lease.forced_release_by,
                    forced_release_reason=lease.forced_release_reason,
                )
            )

    def delete(self, form_id: str) -> None:
        with Session(self._engine) as session, session.begin():
            row = session.get(ReviewLeaseRow, form_id)
            if row is not None:
                session.delete(row)

    @staticmethod
    def _to_model(row: ReviewLeaseRow) -> ReviewLease:
        return ReviewLease(
            form_id=row.form_id,
            owner_id=row.owner_id,
            lease_token=row.lease_token,
            acquired_at=_as_utc(row.acquired_at),
            expires_at=_as_utc(row.expires_at),
            heartbeat_at=_as_utc(row.heartbeat_at),
            forced_release_by=row.forced_release_by,
            forced_release_reason=row.forced_release_reason,
        )


def _as_utc(value: datetime) -> datetime:
    """SQLite does not preserve timezone offsets for DateTime columns."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
