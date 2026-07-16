"""Task inspection and resumable SSE event endpoints."""

import asyncio
from collections.abc import AsyncIterator
from json import dumps

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.dependencies_ds import get_current_actor, get_services
from app.api.schemas.tasks_ds import TaskCreateRequest
from app.modules.identity_access.models_ds import Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.modules.tasks.models_ds import (
    IdempotencyConflict,
    Task,
    TaskCommand,
    TaskEvent,
    TaskStatus,
)
from app.services.container import Services

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


def _require_task_read(request: Request, services: Services) -> str:
    actor = get_current_actor(request, services)
    try:
        PermissionPolicy().require(actor, Permission.TASK_READ)
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail={"code": "PERMISSION_DENIED", "detail": str(error)},
        ) from error
    return actor.actor_id


def _require_task_access(task_id: str, request: Request, services: Services) -> Task:
    try:
        task = services.tasks.get(task_id)
    except KeyError as error:
        raise _task_not_found(task_id) from error
    actor = get_current_actor(request, services)
    policy = PermissionPolicy()
    globally_allowed = policy.allows(actor, Permission.TASK_READ)
    owns_export = (
        task.operation == "XLSX_EXPORT"
        and task.resource_id == "EXPORTS"
        and task.actor_id == actor.actor_id
        and policy.allows(actor, Permission.EXPORT_CREATE)
    )
    if not globally_allowed and not owns_export:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PERMISSION_DENIED",
                "detail": f"Actor {actor.actor_id} cannot read task {task_id}",
            },
        )
    return task


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_task(
    body: TaskCreateRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor_id = _require_task_read(request, services)
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "detail": "Idempotency-Key is required."},
        )
    try:
        task = services.tasks.submit(
            TaskCommand(body.operation, body.resource_id, actor_id, idempotency_key, body.payload)
        )
    except IdempotencyConflict as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_CONFLICT", "detail": str(error)},
        ) from error
    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "status_url": f"/api/v1/tasks/{task.task_id}",
        "events_url": f"/api/v1/tasks/{task.task_id}/events",
    }


@router.get("/{task_id}/events")
def task_events(
    task_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> StreamingResponse:
    _require_task_access(task_id, request, services)
    after = int(request.headers.get("Last-Event-ID", "0"))

    async def stream() -> AsyncIterator[str]:
        last_sequence = after
        terminal = {
            TaskStatus.SUCCEEDED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
            TaskStatus.INTERRUPTED,
        }
        while True:
            events = [
                event
                for event in services.task_store.list_events(task_id)
                if event.sequence > last_sequence
            ]
            for event in events:
                last_sequence = event.sequence
                yield (
                    f"id: {event.sequence}\nevent: {event.event_type}\ndata: "
                    f"{_event_payload(event)}\n\n"
                )
            try:
                task = services.tasks.get(task_id)
            except KeyError:
                return
            if task.status in terminal:
                return
            await asyncio.sleep(0.2)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/{task_id}")
def task_status(
    task_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    task = _require_task_access(task_id, request, services)
    return {
        "task_id": task.task_id,
        "operation": task.operation,
        "resource_id": task.resource_id,
        "status": task.status.value,
        "progress": task.progress,
        "step": task.step,
        "error": task.error,
    }


def _event_payload(event: TaskEvent) -> str:
    return dumps(
        {
            "task_id": event.task_id,
            "progress": event.progress,
            "step": event.step,
        }
    )


def _task_not_found(task_id: str) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "TASK_NOT_FOUND", "detail": f"Unknown task: {task_id}"},
    )
