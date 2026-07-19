"""Controlled binary image import endpoint."""

from hashlib import sha256
from typing import cast
from urllib.parse import unquote
from uuid import uuid4

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from numpy.typing import NDArray

from app.api.dependencies_ds import get_current_actor, get_services
from app.application.import_forms import DuplicateEvidenceError
from app.domain.models import AuditEvent, ReviewStatus
from app.modules.identity_access.models_ds import Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.modules.tasks.models_ds import IdempotencyConflict, Task, TaskCommand, TaskStatus
from app.services.container import Services

router = APIRouter(prefix="/api/v1", tags=["imports"])
_MAX_IMAGE_BYTES = 20 * 1024 * 1024
_SUFFIXES = {"image/jpeg": ".jpg", "image/png": ".png", "image/tiff": ".tiff"}


def _thumbnail_jpeg(image: NDArray[np.uint8]) -> bytes:
    height, width = image.shape[:2]
    scale = min(1.0, 360 / max(height, width))
    thumbnail = cv2.resize(
        image,
        (max(1, round(width * scale)), max(1, round(height * scale))),
        interpolation=cv2.INTER_AREA,
    )
    encoded, content = cv2.imencode(".jpg", thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 82])
    if not encoded:
        raise ValueError("thumbnail encoding failed")
    return content.tobytes()


def _batch_payload(
    batch_id: str,
    tasks: list[Task],
    services: Services,
) -> dict[str, object]:
    ordered = sorted(tasks, key=lambda task: (task.created_at, task.task_id))
    items = [_batch_item_payload(task, services) for task in ordered]
    return {
        "batch_id": batch_id,
        "created_at": ordered[0].created_at.isoformat(),
        "counts": {
            "total": len(items),
            "succeeded": sum(item["status"] == "SUCCEEDED" for item in items),
            "processing": sum(item["status"] == "PROCESSING" for item in items),
            "needs_action": sum(item["status"] == "NEEDS_ACTION" for item in items),
            "failed": sum(item["status"] == "FAILED" for item in items),
        },
        "items": items,
    }


def _batch_item_payload(task: Task, services: Services) -> dict[str, object]:
    if task.status is TaskStatus.SUCCEEDED:
        public_status = "SUCCEEDED"
    elif task.status in {
        TaskStatus.PENDING,
        TaskStatus.RUNNING,
        TaskStatus.RECOVERING,
        TaskStatus.CANCEL_REQUESTED,
    }:
        public_status = "PROCESSING"
    elif task.error == "DUPLICATE_EVIDENCE":
        public_status = "NEEDS_ACTION"
    else:
        public_status = "FAILED"
    form = services.repository.get_form(task.resource_id)
    thumbnail_url: str | None = None
    if form is not None:
        evidence = services.repository.list_evidence(form.form_id)
        thumbnail = next((item for item in evidence if item.type.value == "THUMBNAIL"), None)
        if thumbnail is not None:
            thumbnail_url = f"/api/v1/forms/{form.form_id}/evidence/{thumbnail.file_id}"
    return {
        "task_id": task.task_id,
        "form_id": task.resource_id,
        "file_name": str(task.payload.get("file_name") or task.resource_id),
        "content_type": str(task.payload.get("content_type") or ""),
        "size_bytes": _payload_int(task.payload.get("size_bytes")),
        "width": _payload_int(task.payload.get("width")),
        "height": _payload_int(task.payload.get("height")),
        "status": public_status,
        "review_status": form.review_status.value if form is not None else None,
        "thumbnail_url": thumbnail_url,
        "error": "图片重复，已保留原表单。" if public_status == "NEEDS_ACTION" else task.error,
    }


def _payload_int(value: object) -> int:
    return int(value) if isinstance(value, (str, int, float)) else 0


def _development_admin_allowed(request: Request, services: Services) -> bool:
    actor = get_current_actor(request, services)
    return services.settings.environment.lower() in {"development", "local", "test"} and (
        PermissionPolicy().allows(actor, Permission.FORM_TEST_ADMIN)
    )


def _require_development_admin(request: Request, services: Services) -> None:
    if services.settings.environment.lower() not in {"development", "local", "test"}:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND"})
    actor = get_current_actor(request, services)
    try:
        PermissionPolicy().require(actor, Permission.FORM_TEST_ADMIN)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED"}) from error


def _task_response(task: Task) -> dict[str, object]:
    return {
        "task_id": task.task_id,
        "operation": task.operation,
        "form_id": task.resource_id,
        "status": task.status.value,
        "status_url": f"/api/v1/tasks/{task.task_id}",
        "events_url": f"/api/v1/tasks/{task.task_id}/events",
    }


@router.post("/imports", status_code=status.HTTP_202_ACCEPTED, response_model=None)
async def import_image(
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    import_batch_id: str | None = Header(default=None, alias="X-Import-Batch-ID"),
    original_filename: str | None = Header(default=None, alias="X-Original-Filename"),
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object] | JSONResponse:
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
    decoded = cv2.imdecode(np.frombuffer(content, dtype=np.uint8), cv2.IMREAD_COLOR)
    if decoded is None:
        raise HTTPException(status_code=422, detail={"code": "INVALID_IMAGE_CONTENT"})
    image = cast(NDArray[np.uint8], decoded)
    content_digest = sha256(content).hexdigest()
    form_id = f"FORM-{content_digest[:24]}"
    height, width = image.shape[:2]
    command = TaskCommand(
        "FORM_IMPORT",
        form_id,
        actor.actor_id,
        idempotency_key,
        {
            "sha256": content_digest,
            "content_type": request.headers["content-type"],
            "batch_id": import_batch_id or "",
            "file_name": unquote(original_filename or form_id),
            "size_bytes": len(content),
            "width": int(width),
            "height": int(height),
        },
    )
    idempotent_task = services.task_store.find_idempotent(
        actor.actor_id, command.operation, command.resource_id, idempotency_key
    )
    if idempotent_task is not None:
        return _task_response(idempotent_task)
    existing_evidence = services.repository.find_by_sha256(content_digest)
    if existing_evidence is not None:
        batch_task: Task | None = None
        if import_batch_id:
            try:
                batch_task = services.tasks.submit(command)
                if batch_task.status is TaskStatus.PENDING:
                    services.tasks.start(batch_task.task_id)
                    batch_task = services.tasks.fail(batch_task.task_id, "DUPLICATE_EVIDENCE")
            except IdempotencyConflict as error:
                raise HTTPException(
                    status_code=409, detail={"code": "IDEMPOTENCY_CONFLICT"}
                ) from error
        existing_form = services.repository.get_form(existing_evidence.form_id)
        review_status = (
            existing_form.review_status.value if existing_form is not None else "UNKNOWN"
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={
                "code": "DUPLICATE_EVIDENCE",
                "batch_id": import_batch_id,
                "task_id": batch_task.task_id if batch_task is not None else None,
                "detail": "该图片已经导入，原始证据在退回或作废后仍会保留。",
                "existing_form": {
                    "form_id": existing_evidence.form_id,
                    "review_status": review_status,
                },
                "actions": {
                    "can_open": existing_form is not None,
                    "can_reopen_for_test": (
                        existing_form is not None
                        and existing_form.review_status is ReviewStatus.VOIDED
                        and _development_admin_allowed(request, services)
                    ),
                    "can_purge_for_test": _development_admin_allowed(request, services),
                },
            },
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
            thumbnail = _thumbnail_jpeg(image)
            services.imports.import_thumbnail_bytes(thumbnail, form_id, actor.actor_id)
            services.tasks.report(task.task_id, 60, "classify_template_qr")
            classification = services.recognition.classify_image(form_id, image)
            if classification.source in {"QR", "SHEET_QR"}:
                classified_form = services.repository.get_form(form_id)
                if classified_form is not None:
                    template = services.template_repository.get_version_by_key_version(
                        classified_form.template_id, int(classified_form.template_version)
                    )
                    if template is not None:
                        try:
                            _, canonical_image = (
                                services.recognition.correct_and_record_template_canvas(
                                    form_id,
                                    image,
                                    width=template.page.canonical_width_px,
                                    height=template.page.canonical_height_px,
                                    canonical_dpi=template.page.canonical_dpi,
                                )
                            )
                            services.recognition.record_template_field_crops(
                                form_id, canonical_image, template
                            )
                        except ValueError:
                            services.tasks.report(
                                task.task_id, 70, "correction_skipped_missing_markers"
                            )
            services.tasks.report(task.task_id, 75, "await_recognition_or_review")
            task = services.tasks.succeed(task.task_id)
        except DuplicateEvidenceError as error:
            task = services.tasks.fail(task.task_id, str(error))
            raise HTTPException(status_code=409, detail={"code": "DUPLICATE_EVIDENCE"}) from error
        except Exception as error:
            task = services.tasks.fail(task.task_id, str(error))
            for uri in services.repository.rollback_failed_import(form_id):
                services.evidence_storage.delete_uri(uri)
            raise HTTPException(
                status_code=500,
                detail={"code": "IMPORT_PROCESSING_FAILED"},
            ) from error
    return _task_response(task)


@router.get("/import-batches")
def list_import_batches(
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> list[dict[str, object]]:
    actor = get_current_actor(request, services)
    try:
        PermissionPolicy().require(actor, Permission.FORM_READ)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED"}) from error
    tasks = services.tasks.list_operation_tasks("FORM_IMPORT", tuple(TaskStatus))
    grouped: dict[str, list[Task]] = {}
    for task in tasks:
        batch_id = str(task.payload.get("batch_id") or "")
        if batch_id:
            grouped.setdefault(batch_id, []).append(task)
    return [
        _batch_payload(batch_id, items, services)
        for batch_id, items in sorted(
            grouped.items(),
            key=lambda item: min(task.created_at for task in item[1]),
            reverse=True,
        )
    ]


@router.get("/images")
def list_imported_images(
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> list[dict[str, object]]:
    actor = get_current_actor(request, services)
    try:
        PermissionPolicy().require(actor, Permission.FORM_READ)
    except PermissionError as error:
        raise HTTPException(status_code=403, detail={"code": "PERMISSION_DENIED"}) from error
    tasks = services.tasks.list_operation_tasks("FORM_IMPORT", tuple(TaskStatus))
    file_names = {
        task.resource_id: str(task.payload.get("file_name") or task.resource_id)
        for task in tasks
    }
    results: list[dict[str, object]] = []
    for form in services.repository.list_forms():
        evidence = services.repository.list_evidence(form.form_id)
        original = next(
            (item for item in evidence if item.type.value == "ORIGINAL_IMAGE"), None
        )
        thumbnail = next((item for item in evidence if item.type.value == "THUMBNAIL"), None)
        if original is None:
            continue
        selected = thumbnail or original
        results.append(
            {
                "form_id": form.form_id,
                "file_name": file_names.get(form.form_id, form.form_id),
                "review_status": form.review_status.value,
                "template_id": form.template_id,
                "template_version": form.template_version,
                "created_at": form.created_at.isoformat(),
                "thumbnail_url": (
                    f"/api/v1/forms/{form.form_id}/evidence/{selected.file_id}"
                ),
                "original_url": (
                    f"/api/v1/forms/{form.form_id}/evidence/{original.file_id}"
                ),
            }
        )
    return sorted(results, key=lambda item: str(item["created_at"]), reverse=True)


@router.post("/imports/existing/{form_id}/reopen-test")
def reopen_voided_form_for_test(
    form_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, str]:
    _require_development_admin(request, services)
    actor = get_current_actor(request, services)
    form = services.repository.get_form(form_id)
    if form is None:
        raise HTTPException(status_code=404, detail={"code": "FORM_NOT_FOUND"})
    if form.review_status is not ReviewStatus.VOIDED:
        raise HTTPException(status_code=409, detail={"code": "FORM_NOT_VOIDED"})
    next_status = (
        ReviewStatus.NEEDS_CLASSIFICATION
        if form.template_id == "UNKNOWN"
        else ReviewStatus.CLASSIFIED
    )
    services.repository.set_review_status(form_id, next_status)
    services.repository.add_audit_event(
        AuditEvent(
            event_id=f"EVENT-{uuid4().hex}",
            form_id=form_id,
            event_type="REOPEN_FOR_LOCAL_TEST",
            actor_id=actor.actor_id,
            before={"review_status": ReviewStatus.VOIDED.value},
            after={"review_status": next_status.value},
            reason="管理员在开发环境中重新启用已作废表单进行测试",
        )
    )
    return {"form_id": form_id, "review_status": next_status.value}


@router.delete("/imports/existing/{form_id}")
def purge_form_for_test(
    form_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require_development_admin(request, services)
    try:
        uris = services.repository.purge_test_form(form_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail={"code": "FORM_NOT_FOUND"}) from error
    for uri in uris:
        services.evidence_storage.delete_uri(uri)
    return {"form_id": form_id, "deleted": True, "deleted_evidence_count": len(uris)}
