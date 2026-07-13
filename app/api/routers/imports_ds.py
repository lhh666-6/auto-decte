"""Controlled binary image import endpoint."""

from hashlib import sha256

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.api.dependencies_ds import get_current_actor, get_services
from app.application.import_forms import DuplicateEvidenceError
from app.modules.identity_access.models_ds import Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.modules.tasks.models_ds import IdempotencyConflict, TaskCommand, TaskStatus
from app.services.container import Services

router = APIRouter(prefix="/api/v1", tags=["imports"])
_MAX_IMAGE_BYTES = 20 * 1024 * 1024
_SUFFIXES = {"image/jpeg": ".jpg", "image/png": ".png", "image/tiff": ".tiff"}


@router.post("/imports", status_code=status.HTTP_202_ACCEPTED)
async def import_image(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = get_current_actor(request, services)
    try:
        PermissionPolicy().require(actor, Permission.FORM_IMPORT)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED"}) from error
    if not idempotency_key:
        raise HTTPException(status_code=400, detail={"code": "IDEMPOTENCY_KEY_REQUIRED"})
    suffix = _SUFFIXES.get(request.headers.get("content-type", "").split(";", 1)[0].lower())
    if suffix is None:
        raise HTTPException(status_code=415, detail={"code": "UNSUPPORTED_IMAGE_TYPE"})
    content = await request.body()
    if not content or len(content) > _MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail={"code": "INVALID_IMAGE_SIZE"})
    image = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail={"code": "INVALID_IMAGE_CONTENT"})
    content_digest = sha256(content).hexdigest()
    form_id = f"FORM-{content_digest[:24]}"
    command = TaskCommand(
        "FORM_IMPORT",
        form_id,
        actor.actor_id,
        idempotency_key,
        {"sha256": content_digest, "content_type": request.headers["content-type"]},
    )
    try:
        task = services.tasks.submit(command)
    except IdempotencyConflict as error:
        raise HTTPException(status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT"}) from error
    if task.status is TaskStatus.PENDING:
        try:
            services.tasks.start(task.task_id)
            services.tasks.report(task.task_id, 25, "store_original_evidence")
            services.imports.import_image_bytes(
                content, suffix, form_id, "UNKNOWN", "0", actor.actor_id
            )
            services.tasks.report(task.task_id, 60, "classify_template_qr")
            services.recognition.classify_image(form_id, image)
            services.tasks.report(task.task_id, 75, "await_recognition_or_review")
            task = services.tasks.succeed(task.task_id)
        except DuplicateEvidenceError as error:
            task = services.tasks.fail(task.task_id, str(error))
            raise HTTPException(status_code=409, detail={"code": "DUPLICATE_EVIDENCE"}) from error
    return {
        "task_id": task.task_id,
        "operation": task.operation,
        "form_id": task.resource_id,
        "status": task.status.value,
        "status_url": f"/api/v1/tasks/{task.task_id}",
        "events_url": f"/api/v1/tasks/{task.task_id}/events",
    }
