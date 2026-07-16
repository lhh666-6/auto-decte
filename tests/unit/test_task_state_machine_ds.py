import pytest

from app.modules.tasks.models_ds import InvalidTaskTransition, Task, TaskStatus


def test_pending_task_moves_to_running_then_succeeded() -> None:
    task = Task.new("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {"mode": "full"})

    running = task.transition(TaskStatus.RUNNING)
    succeeded = running.transition(TaskStatus.SUCCEEDED)

    assert running.status is TaskStatus.RUNNING
    assert succeeded.status is TaskStatus.SUCCEEDED
    assert succeeded.progress == 100


def test_task_rejects_terminal_transition_and_can_cancel() -> None:
    task = Task.new("FORM_RECOGNITION", "FORM-1", "operator-1", "key-1", {})

    cancelled = task.transition(TaskStatus.CANCEL_REQUESTED).transition(TaskStatus.CANCELLED)
    assert cancelled.status is TaskStatus.CANCELLED
    with pytest.raises(InvalidTaskTransition):
        cancelled.transition(TaskStatus.RUNNING)


def test_recovery_owner_can_finish_fail_or_be_interrupted_again() -> None:
    task = Task.new("XLSX_EXPORT", "exports", "finance", "recover", {})
    running = task.transition(TaskStatus.RUNNING)
    with pytest.raises(InvalidTaskTransition):
        running.transition(TaskStatus.RECOVERING)
    recovering = running.transition(TaskStatus.INTERRUPTED).transition(
        TaskStatus.RECOVERING
    )

    assert recovering.transition(TaskStatus.SUCCEEDED).status is TaskStatus.SUCCEEDED
    assert recovering.transition(TaskStatus.FAILED).status is TaskStatus.FAILED
    assert recovering.transition(TaskStatus.INTERRUPTED).status is TaskStatus.INTERRUPTED
    assert recovering.status is TaskStatus.RECOVERING
