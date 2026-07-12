from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from app.adapters.database.models import Base
from app.infrastructure.database.sqlite_ds import create_sqlite_engine
from app.infrastructure.tasks.in_process_ds import InProcessTaskRunner
from app.infrastructure.tasks.sqlite_store_ds import SqliteTaskStore
from app.modules.tasks.models_ds import IdempotencyConflict, TaskCommand, TaskStatus
from app.modules.tasks.service_ds import TaskService


def build_service(tmp_path: Path) -> tuple[TaskService, SqliteTaskStore]:
    engine = create_sqlite_engine(tmp_path / "demo.db")
    Base.metadata.create_all(engine)
    store = SqliteTaskStore(engine)
    return TaskService(store), store


def test_same_idempotency_key_and_payload_returns_existing_task(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    command = TaskCommand("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {"mode": "full"})

    assert service.submit(command) == service.submit(command)


def test_same_key_with_different_payload_is_conflict(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    service.submit(
        TaskCommand("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {"mode": "full"})
    )

    with pytest.raises(IdempotencyConflict):
        service.submit(
            TaskCommand("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {"mode": "quick"})
        )


def test_task_events_have_incrementing_sequences(tmp_path: Path) -> None:
    service, store = build_service(tmp_path)
    task = service.submit(TaskCommand("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {}))
    service.start(task.task_id)
    service.report(task.task_id, 50, "recognizing")
    service.succeed(task.task_id)

    assert [event.sequence for event in store.list_events(task.task_id)] == [1, 2, 3, 4]


def test_recovery_marks_running_tasks_interrupted(tmp_path: Path) -> None:
    service, store = build_service(tmp_path)
    task = service.submit(TaskCommand("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {}))
    service.start(task.task_id)

    recovered = service.recover_interrupted()

    assert recovered == [task.task_id]
    assert store.get(task.task_id).status is TaskStatus.INTERRUPTED  # type: ignore[union-attr]


def test_runner_reports_progress_and_marks_task_succeeded(tmp_path: Path) -> None:
    service, store = build_service(tmp_path)
    runner = InProcessTaskRunner(service, max_workers=1, queue_capacity=1)

    task = runner.submit(
        TaskCommand("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {}),
        lambda context: context.report(50, "recognizing"),
    )
    runner.wait(task.task_id, timeout=2)
    runner.shutdown()

    assert store.get(task.task_id).status is TaskStatus.SUCCEEDED  # type: ignore[union-attr]


def test_failed_task_can_be_retried_from_pending_state(tmp_path: Path) -> None:
    service, store = build_service(tmp_path)
    runner = InProcessTaskRunner(service, max_workers=1, queue_capacity=1)
    task = runner.submit(
        TaskCommand("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {}),
        lambda context: (_ for _ in ()).throw(RuntimeError("recognition error")),
    )

    with pytest.raises(RuntimeError, match="recognition error"):
        runner.wait(task.task_id, timeout=2)
    runner.shutdown()
    retried = service.retry(task.task_id)

    assert store.get(task.task_id).status is TaskStatus.PENDING  # type: ignore[union-attr]
    assert retried.status is TaskStatus.PENDING


def test_store_allocates_unique_event_sequences_for_concurrent_writers(tmp_path: Path) -> None:
    service, store = build_service(tmp_path)
    task = service.submit(TaskCommand("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {}))

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(store.append_next_event, task, "PROGRESS") for _ in range(2)]
        for future in futures:
            future.result()

    assert [event.sequence for event in store.list_events(task.task_id)] == [1, 2, 3]
