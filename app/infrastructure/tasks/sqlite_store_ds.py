"""SQLite task store with append-only progress events."""

from datetime import UTC, datetime
from threading import Lock
from typing import Any, cast
from uuid import uuid4

from sqlalchemy import Engine, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from app.adapters.database.models import TaskEventRow, TaskRow
from app.modules.tasks.models_ds import Task, TaskEvent, TaskStatus


class SqliteTaskStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._event_lock = Lock()

    def get(self, task_id: str) -> Task | None:
        with Session(self._engine) as session:
            row = session.get(TaskRow, task_id)
            return self._to_task(row) if row is not None else None

    def find_idempotent(
        self, actor_id: str, operation: str, resource_id: str, key: str
    ) -> Task | None:
        statement = select(TaskRow).where(
            TaskRow.actor_id == actor_id,
            TaskRow.operation == operation,
            TaskRow.resource_id == resource_id,
            TaskRow.idempotency_key == key,
        )
        with Session(self._engine) as session:
            row = session.scalar(statement)
            return self._to_task(row) if row is not None else None

    def create(self, task: Task) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(self._to_row(task))

    def claim(self, task_id: str) -> Task | None:
        """Atomically move one pending task to running."""
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            result = cast(
                CursorResult[Any],
                session.execute(
                    update(TaskRow)
                    .where(
                        TaskRow.task_id == task_id,
                        TaskRow.status == TaskStatus.PENDING.value,
                    )
                    .values(status=TaskStatus.RUNNING.value, updated_at=now)
                ),
            )
            if result.rowcount != 1:
                return None
            row = session.get(TaskRow, task_id)
            assert row is not None
            return self._to_task(row)

    def claim_recovery(self, task_id: str) -> Task | None:
        """Atomically give one recovery worker ownership of an interrupted export."""
        now = datetime.now(UTC)
        with Session(self._engine) as session, session.begin():
            result = cast(
                CursorResult[Any],
                session.execute(
                    update(TaskRow)
                    .where(
                        TaskRow.task_id == task_id,
                        TaskRow.status.in_(
                            (
                                TaskStatus.RUNNING.value,
                                TaskStatus.INTERRUPTED.value,
                            )
                        ),
                    )
                    .values(status=TaskStatus.RECOVERING.value, updated_at=now)
                ),
            )
            if result.rowcount != 1:
                return None
            row = session.get(TaskRow, task_id)
            assert row is not None
            return self._to_task(row)

    def reconcile_succeeded(
        self, task_id: str, detail: dict[str, object] | None = None
    ) -> Task:
        """Repair a task when an already-committed result is authoritative."""
        with self._event_lock, Session(self._engine) as session, session.begin():
            row = session.get(TaskRow, task_id)
            if row is None:
                raise KeyError(task_id)
            if row.status != TaskStatus.SUCCEEDED.value or row.progress != 100:
                now = datetime.now(UTC)
                row.status = TaskStatus.SUCCEEDED.value
                row.progress = 100
                row.error = None
                row.updated_at = now
                sequence = (
                    session.scalar(
                        select(func.max(TaskEventRow.sequence)).where(
                            TaskEventRow.task_id == task_id
                        )
                    )
                    or 0
                ) + 1
                session.add(
                    TaskEventRow(
                        event_id=f"TASK-EVENT-{uuid4().hex}",
                        task_id=task_id,
                        sequence=sequence,
                        event_type=TaskStatus.SUCCEEDED.value,
                        progress=100,
                        step=row.step,
                        detail=detail,
                        created_at=now,
                    )
                )
            return self._to_task(row)

    def update(self, task: Task) -> None:
        with Session(self._engine) as session, session.begin():
            row = session.get(TaskRow, task.task_id)
            if row is None:
                raise KeyError(task.task_id)
            row.status = task.status.value
            row.progress = task.progress
            row.step = task.step
            row.error = task.error
            row.updated_at = task.updated_at

    def append_event(self, event: TaskEvent) -> None:
        with Session(self._engine) as session, session.begin():
            session.add(
                TaskEventRow(
                    event_id=event.event_id,
                    task_id=event.task_id,
                    sequence=event.sequence,
                    event_type=event.event_type,
                    progress=event.progress,
                    step=event.step,
                    detail=event.detail,
                    created_at=event.created_at,
                )
            )

    def append_next_event(
        self,
        task: Task,
        event_type: str,
        detail: dict[str, object] | None = None,
    ) -> TaskEvent:
        """Allocate and append an event while serialising local task writers."""
        with self._event_lock, Session(self._engine) as session, session.begin():
            sequence = (
                session.scalar(
                    select(func.max(TaskEventRow.sequence)).where(
                        TaskEventRow.task_id == task.task_id
                    )
                )
                or 0
            ) + 1
            event = TaskEvent(
                event_id=f"TASK-EVENT-{uuid4().hex}",
                task_id=task.task_id,
                sequence=sequence,
                event_type=event_type,
                progress=task.progress,
                step=task.step,
                detail=detail,
                created_at=datetime.now(UTC),
            )
            session.add(
                TaskEventRow(
                    event_id=event.event_id,
                    task_id=event.task_id,
                    sequence=event.sequence,
                    event_type=event.event_type,
                    progress=event.progress,
                    step=event.step,
                    detail=event.detail,
                    created_at=event.created_at,
                )
            )
            return event

    def list_events(self, task_id: str) -> list[TaskEvent]:
        statement = (
            select(TaskEventRow)
            .where(TaskEventRow.task_id == task_id)
            .order_by(TaskEventRow.sequence)
        )
        with Session(self._engine) as session:
            return [
                TaskEvent(
                    event_id=row.event_id,
                    task_id=row.task_id,
                    sequence=row.sequence,
                    event_type=row.event_type,
                    progress=row.progress,
                    step=row.step,
                    detail=row.detail,
                    created_at=_as_utc(row.created_at),
                )
                for row in session.scalars(statement)
            ]

    def latest_event(self, task_id: str, event_type: str) -> TaskEvent | None:
        statement = (
            select(TaskEventRow)
            .where(
                TaskEventRow.task_id == task_id,
                TaskEventRow.event_type == event_type,
            )
            .order_by(TaskEventRow.sequence.desc())
            .limit(1)
        )
        with Session(self._engine) as session:
            row = session.scalar(statement)
            if row is None:
                return None
            return TaskEvent(
                event_id=row.event_id,
                task_id=row.task_id,
                sequence=row.sequence,
                event_type=row.event_type,
                progress=row.progress,
                step=row.step,
                detail=row.detail,
                created_at=_as_utc(row.created_at),
            )

    def next_event(
        self, task: Task, event_type: str, detail: dict[str, object] | None = None
    ) -> TaskEvent:
        statement = select(func.max(TaskEventRow.sequence)).where(
            TaskEventRow.task_id == task.task_id
        )
        with Session(self._engine) as session:
            sequence = (session.scalar(statement) or 0) + 1
        return TaskEvent(
            event_id=f"TASK-EVENT-{uuid4().hex}",
            task_id=task.task_id,
            sequence=sequence,
            event_type=event_type,
            progress=task.progress,
            step=task.step,
            detail=detail,
            created_at=datetime.now(UTC),
        )

    def list_by_status(self, status: str) -> list[Task]:
        statement = select(TaskRow).where(TaskRow.status == status).order_by(TaskRow.created_at)
        with Session(self._engine) as session:
            return [self._to_task(row) for row in session.scalars(statement)]

    def list_by_operation_statuses(
        self, operation: str, statuses: tuple[str, ...]
    ) -> list[Task]:
        if not statuses:
            return []
        statement = (
            select(TaskRow)
            .where(
                TaskRow.operation == operation,
                TaskRow.status.in_(statuses),
            )
            .order_by(TaskRow.created_at, TaskRow.task_id)
        )
        with Session(self._engine) as session:
            return [self._to_task(row) for row in session.scalars(statement)]

    @staticmethod
    def _to_row(task: Task) -> TaskRow:
        return TaskRow(
            task_id=task.task_id,
            operation=task.operation,
            resource_id=task.resource_id,
            actor_id=task.actor_id,
            idempotency_key=task.idempotency_key,
            payload=task.payload,
            payload_hash=task.payload_hash,
            status=task.status.value,
            progress=task.progress,
            step=task.step,
            error=task.error,
            created_at=task.created_at,
            updated_at=task.updated_at,
        )

    @staticmethod
    def _to_task(row: TaskRow) -> Task:
        return Task(
            task_id=row.task_id,
            operation=row.operation,
            resource_id=row.resource_id,
            actor_id=row.actor_id,
            idempotency_key=row.idempotency_key,
            payload=row.payload,
            payload_hash=row.payload_hash,
            status=TaskStatus(row.status),
            progress=row.progress,
            step=row.step,
            error=row.error,
            created_at=_as_utc(row.created_at),
            updated_at=_as_utc(row.updated_at),
        )


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
