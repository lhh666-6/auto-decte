"""Bounded in-process task runner for local deployments."""

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import BoundedSemaphore, Lock

from app.modules.tasks.models import Task, TaskCommand, TaskStatus
from app.modules.tasks.service import TaskService


@dataclass(frozen=True, slots=True)
class TaskContext:
    task_id: str
    _service: TaskService

    def report(self, progress: int, step: str | None = None) -> Task:
        return self._service.report(self.task_id, progress, step)

    def cancel_requested(self) -> bool:
        return self._service.cancel_requested(self.task_id)


TaskHandler = Callable[[TaskContext], None]


class InProcessTaskRunner:
    def __init__(self, service: TaskService, *, max_workers: int, queue_capacity: int) -> None:
        self._service = service
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="form-task")
        self._capacity = BoundedSemaphore(queue_capacity)
        self._futures: dict[str, Future[None]] = {}
        self._lock = Lock()

    def submit(self, command: TaskCommand, handler: TaskHandler) -> Task:
        task = self._service.submit(command)
        if task.status is not TaskStatus.PENDING:
            return task
        if not self._capacity.acquire(blocking=False):
            raise RuntimeError("Task queue is full")
        future = self._executor.submit(self._run, task.task_id, handler)
        with self._lock:
            self._futures[task.task_id] = future
        return task

    def wait(self, task_id: str, timeout: float | None = None) -> None:
        with self._lock:
            future = self._futures.get(task_id)
        if future is None:
            raise KeyError(task_id)
        future.result(timeout=timeout)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True)

    def _run(self, task_id: str, handler: TaskHandler) -> None:
        try:
            self._service.start(task_id)
            context = TaskContext(task_id, self._service)
            handler(context)
            if context.cancel_requested():
                self._service.cancel(task_id)
            else:
                self._service.succeed(task_id)
        except Exception as error:
            task = self._service.get(task_id)
            if task.status is TaskStatus.RUNNING:
                self._service.fail(task_id, str(error))
            raise
        finally:
            self._capacity.release()
