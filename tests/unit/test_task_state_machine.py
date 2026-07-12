import pytest

from app.modules.tasks.models import InvalidTaskTransition, Task, TaskStatus


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
