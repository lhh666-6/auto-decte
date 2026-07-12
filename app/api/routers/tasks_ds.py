"""Task inspection and resumable SSE event endpoints."""

from json import dumps

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from app.api.dependencies_ds import get_current_actor, get_services
from app.api.schemas.tasks_ds import TaskCreateRequest
from app.modules.identity_access.models_ds import Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.modules.tasks.models_ds import IdempotencyConflict, TaskCommand, TaskEvent
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
    _require_task_read(request, services)
    after = int(request.headers.get("Last-Event-ID", "0"))
    events = [event for event in services.task_store.list_events(task_id) if event.sequence > after]

    def stream() -> str:
        return "".join(
            f"id: {event.sequence}\nevent: {event.event_type}\ndata: {_event_payload(event)}\n\n"
            for event in events
        )

    return StreamingResponse(iter([stream()]), media_type="text/event-stream")


def _event_payload(event: TaskEvent) -> str:
    return dumps(
        {
            "task_id": event.task_id,
            "progress": event.progress,
            "step": event.step,
        }
    )
