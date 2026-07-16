"""Task application service for idempotency, state changes and recovery."""

from app.infrastructure.tasks.sqlite_store_ds import SqliteTaskStore
from app.modules.tasks.models_ds import (
    IdempotencyConflict,
    Task,
    TaskClaimConflict,
    TaskCommand,
    TaskStatus,
)


class TaskService:
    def __init__(self, store: SqliteTaskStore) -> None:
        self._store = store

    def submit(self, command: TaskCommand) -> Task:
        existing = self._store.find_idempotent(
            command.actor_id, command.operation, command.resource_id, command.idempotency_key
        )
        if existing is not None:
            if existing.payload_hash != command.payload_hash:
                raise IdempotencyConflict("Idempotency key has a different payload")
            return existing
        task = Task.new(
            command.operation,
            command.resource_id,
            command.actor_id,
            command.idempotency_key,
            command.payload,
        )
        self._store.create(task)
        self._append(task, "CREATED")
        return task

    def start(self, task_id: str) -> Task:
        return self._transition(task_id, TaskStatus.RUNNING)

    def claim(self, task_id: str) -> Task:
        task = self._store.claim(task_id)
        if task is None:
            raise TaskClaimConflict(f"Task is not pending: {task_id}")
        self._append(task, TaskStatus.RUNNING.value)
        return task

    def reconcile_succeeded(
        self, task_id: str, detail: dict[str, object] | None = None
    ) -> Task:
        return self._store.reconcile_succeeded(task_id, detail)

    def succeed(self, task_id: str) -> Task:
        return self._transition(task_id, TaskStatus.SUCCEEDED)

    def fail(self, task_id: str, error: str) -> Task:
        task = self._require(task_id).transition(TaskStatus.FAILED, error=error)
        self._store.update(task)
        self._append(task, TaskStatus.FAILED.value)
        return task

    def request_cancel(self, task_id: str) -> Task:
        return self._transition(task_id, TaskStatus.CANCEL_REQUESTED)

    def cancel(self, task_id: str) -> Task:
        return self._transition(task_id, TaskStatus.CANCELLED)

    def retry(self, task_id: str) -> Task:
        return self._transition(task_id, TaskStatus.PENDING)

    def report(self, task_id: str, progress: int, step: str | None) -> Task:
        task = self._require(task_id).report(progress, step)
        self._store.update(task)
        self._append(task, "PROGRESS")
        return task

    def get(self, task_id: str) -> Task:
        return self._require(task_id)

    def cancel_requested(self, task_id: str) -> bool:
        return self._require(task_id).status is TaskStatus.CANCEL_REQUESTED

    def recover_interrupted(self) -> list[str]:
        recovered: list[str] = []
        for task in self._store.list_by_status(TaskStatus.RUNNING.value):
            interrupted = task.transition(TaskStatus.INTERRUPTED)
            self._store.update(interrupted)
            self._append(interrupted, "INTERRUPTED")
            recovered.append(task.task_id)
        return recovered

    def _transition(self, task_id: str, target: TaskStatus) -> Task:
        task = self._require(task_id).transition(target)
        self._store.update(task)
        self._append(task, target.value)
        return task

    def _require(self, task_id: str) -> Task:
        task = self._store.get(task_id)
        if task is None:
            raise KeyError(task_id)
        return task

    def _append(self, task: Task, event_type: str) -> None:
        self._store.append_next_event(task, event_type)
