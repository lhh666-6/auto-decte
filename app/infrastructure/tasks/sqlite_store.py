"""SQLite task store with append-only progress events."""

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.adapters.database.models import TaskEventRow, TaskRow
from app.modules.tasks.models import Task, TaskEvent, TaskStatus


class SqliteTaskStore:
    def __init__(self, engine: Engine) -> None:
        self._engine = engine

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
