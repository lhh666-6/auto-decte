"""Persistent task state machine and command value objects."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from json import dumps
from uuid import uuid4


class TaskStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    INTERRUPTED = "INTERRUPTED"


class InvalidTaskTransition(RuntimeError):
    pass


class IdempotencyConflict(RuntimeError):
    pass


_TRANSITIONS: dict[TaskStatus, frozenset[TaskStatus]] = {
    TaskStatus.PENDING: frozenset({TaskStatus.RUNNING, TaskStatus.CANCEL_REQUESTED}),
    TaskStatus.RUNNING: frozenset(
        {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCEL_REQUESTED,
            TaskStatus.INTERRUPTED,
        }
    ),
    TaskStatus.CANCEL_REQUESTED: frozenset({TaskStatus.CANCELLED}),
    TaskStatus.FAILED: frozenset({TaskStatus.PENDING}),
    TaskStatus.INTERRUPTED: frozenset({TaskStatus.PENDING}),
    TaskStatus.SUCCEEDED: frozenset(),
    TaskStatus.CANCELLED: frozenset(),
}


@dataclass(frozen=True, slots=True)
class TaskCommand:
    operation: str
    resource_id: str
    actor_id: str
    idempotency_key: str
    payload: dict[str, object]

    @property
    def payload_hash(self) -> str:
        body = dumps(self.payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return sha256(body.encode()).hexdigest()


@dataclass(frozen=True, slots=True)
class Task:
    task_id: str
    operation: str
    resource_id: str
    actor_id: str
    idempotency_key: str
    payload: dict[str, object]
    payload_hash: str
    status: TaskStatus
    progress: int
    step: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def new(
        cls,
        operation: str,
        resource_id: str,
        actor_id: str,
        idempotency_key: str,
        payload: dict[str, object],
    ) -> "Task":
        now = datetime.now(UTC)
        command = TaskCommand(operation, resource_id, actor_id, idempotency_key, payload)
        return cls(
            task_id=f"TASK-{uuid4().hex}",
            operation=operation,
            resource_id=resource_id,
            actor_id=actor_id,
            idempotency_key=idempotency_key,
            payload=payload,
            payload_hash=command.payload_hash,
            status=TaskStatus.PENDING,
            progress=0,
            step=None,
            error=None,
            created_at=now,
            updated_at=now,
        )

    def transition(self, target: TaskStatus, *, error: str | None = None) -> "Task":
        if target not in _TRANSITIONS[self.status]:
            raise InvalidTaskTransition(f"Cannot transition {self.status} to {target}")
        return replace(
            self,
            status=target,
            progress=100 if target is TaskStatus.SUCCEEDED else self.progress,
            error=error,
            updated_at=datetime.now(UTC),
        )

    def report(self, progress: int, step: str | None) -> "Task":
        if self.status is not TaskStatus.RUNNING:
            raise InvalidTaskTransition("Progress can only be reported for running tasks")
        if not 0 <= progress <= 100 or progress < self.progress:
            raise ValueError("Progress must be monotonically increasing from 0 to 100")
        return replace(self, progress=progress, step=step, updated_at=datetime.now(UTC))


@dataclass(frozen=True, slots=True)
class TaskEvent:
    event_id: str
    task_id: str
    sequence: int
    event_type: str
    progress: int | None
    step: str | None
    detail: dict[str, object] | None
    created_at: datetime
