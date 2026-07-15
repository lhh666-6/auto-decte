"""Persistence adapter for review leases, drafts and queue claims."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any, cast

from sqlalchemy import Engine, or_, select, update
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.adapters.database.models import FormRow, ReviewDraftRow, ReviewLeaseRow
from app.domain.models import ReviewStatus
from app.modules.review.models_ds import ReviewDraft, ReviewLease


class SqlAlchemyReviewLeaseRepository:
    def __init__(self, engine: Engine, session: Session | None = None) -> None:
        self._engine = engine
        self._session = session

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        if self._session is not None:
            yield self._session
            return
        with Session(self._engine) as session, session.begin():
            yield session

    @contextmanager
    def _read_session(self) -> Iterator[Session]:
        if self._session is not None:
            yield self._session
            return
        with Session(self._engine) as session:
            yield session

    def get(self, form_id: str) -> ReviewLease | None:
        with self._read_session() as session:
            row = session.get(ReviewLeaseRow, form_id)
            return self._to_model(row) if row is not None else None

    def save(self, lease: ReviewLease) -> None:
        with self._transaction() as session:
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

    def try_acquire(self, lease: ReviewLease, now: datetime) -> bool:
        """Atomically acquire a lease if no live owner currently holds the form."""
        values = {
            "form_id": lease.form_id,
            "owner_id": lease.owner_id,
            "lease_token": lease.lease_token,
            "acquired_at": lease.acquired_at,
            "expires_at": lease.expires_at,
            "heartbeat_at": lease.heartbeat_at,
            "forced_release_by": lease.forced_release_by,
            "forced_release_reason": lease.forced_release_reason,
        }
        statement = insert(ReviewLeaseRow).values(**values)
        statement = statement.on_conflict_do_update(
            index_elements=[ReviewLeaseRow.form_id],
            set_=values,
            where=ReviewLeaseRow.expires_at <= now,
        )
        with self._transaction() as session:
            result = cast(CursorResult[Any], session.execute(statement))
            return result.rowcount == 1

    def restore_owned(
        self, form_id: str, owner_id: str, now: datetime, expires_at: datetime
    ) -> ReviewLease | None:
        """Atomically restore and renew a live lease held by the same actor."""
        statement = (
            update(ReviewLeaseRow)
            .where(
                ReviewLeaseRow.form_id == form_id,
                ReviewLeaseRow.owner_id == owner_id,
                ReviewLeaseRow.expires_at > now,
            )
            .values(heartbeat_at=now, expires_at=expires_at)
        )
        with self._transaction() as session:
            result = cast(CursorResult[Any], session.execute(statement))
            if result.rowcount != 1:
                return None
            row = session.get(ReviewLeaseRow, form_id)
            return self._to_model(row) if row is not None else None

    def delete(self, form_id: str) -> None:
        with self._transaction() as session:
            row = session.get(ReviewLeaseRow, form_id)
            if row is not None:
                session.delete(row)

    def get_draft(self, form_id: str) -> ReviewDraft | None:
        with self._read_session() as session:
            row = session.get(ReviewDraftRow, form_id)
            if row is None:
                return None
            return ReviewDraft(
                form_id=row.form_id,
                expected_version=row.expected_version,
                values=dict(row.values),
                saved_by=row.saved_by,
                updated_at=_as_utc(row.updated_at),
            )

    def save_draft(self, draft: ReviewDraft) -> None:
        with self._transaction() as session:
            session.merge(
                ReviewDraftRow(
                    form_id=draft.form_id,
                    expected_version=draft.expected_version,
                    values=draft.values,
                    saved_by=draft.saved_by,
                    updated_at=draft.updated_at,
                )
            )

    def delete_draft(self, form_id: str) -> None:
        with self._transaction() as session:
            row = session.get(ReviewDraftRow, form_id)
            if row is not None:
                session.delete(row)

    def next_claimable_form_id(
        self,
        *,
        review_statuses: tuple[ReviewStatus, ...],
        exclude_form_id: str,
        now: datetime,
    ) -> str | None:
        """Select the first unleased queue item using the product's stable order."""
        statement = (
            select(FormRow.form_id)
            .outerjoin(ReviewLeaseRow, ReviewLeaseRow.form_id == FormRow.form_id)
            .where(
                FormRow.review_status.in_([status.value for status in review_statuses]),
                FormRow.form_id != exclude_form_id,
                or_(ReviewLeaseRow.form_id.is_(None), ReviewLeaseRow.expires_at <= now),
            )
            .order_by(FormRow.priority.desc(), FormRow.created_at, FormRow.form_id)
            .limit(1)
        )
        with self._read_session() as session:
            return session.scalar(statement)

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
