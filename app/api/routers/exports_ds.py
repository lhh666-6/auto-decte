"""Authorized template-driven XLSX export endpoints."""

import re
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from fastapi.responses import Response

from app.adapters.database.report_definition_repository_ds import ReportDefinitionConflict
from app.api.dependencies_ds import get_current_actor, get_services
from app.api.schemas.exports_ds import (
    ExportBatchResponse,
    ExportCreateRequest,
    ExportPreviewResponse,
    ReportDefinitionCreateRequest,
    ReportDefinitionResponse,
)
from app.application.query_forms import FormFilters
from app.domain.models import ExportBatch, ExportStatus, ReviewStatus, thaw_json
from app.modules.identity_access.models_ds import Actor, Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.modules.reporting.models_ds import (
    ExportPreview,
    ExportPreviewItem,
    FixedCellMapping,
    FixedTableColumn,
    FixedTableMapping,
    ReportAggregate,
    ReportColumn,
    ReportDefinition,
)
from app.modules.tasks.models_ds import IdempotencyConflict, TaskCommand, TaskStatus
from app.services.container import Services

router = APIRouter(prefix="/api/v1/exports", tags=["exports"])


def _require(actor: Actor, permission: Permission) -> None:
    try:
        PermissionPolicy().require(actor, permission)
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail={"code": "PERMISSION_DENIED", "detail": str(error)},
        ) from error


@router.get(
    "/report-definitions",
    response_model=list[ReportDefinitionResponse],
)
def list_report_definitions(
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> list[dict[str, object]]:
    actor = get_current_actor(request, services)
    _require(actor, Permission.EXPORT_PREVIEW)
    return [
        _report_definition_payload(item) for item in services.report_definition_repository.list()
    ]


@router.get(
    "/report-definitions/{definition_id}",
    response_model=ReportDefinitionResponse,
)
def get_report_definition(
    definition_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = get_current_actor(request, services)
    _require(actor, Permission.EXPORT_PREVIEW)
    definition = services.report_definition_repository.get(definition_id)
    if definition is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "REPORT_DEFINITION_NOT_FOUND",
                "detail": "Report definition was not found.",
            },
        )
    return _report_definition_payload(definition)


@router.post(
    "/report-definitions",
    response_model=ReportDefinitionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_report_definition(
    body: ReportDefinitionCreateRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = get_current_actor(request, services)
    _require(actor, Permission.EXPORT_CREATE)
    try:
        definition = _report_definition_from_request(body)
        services.report_definition_repository.add(definition)
    except ReportDefinitionConflict as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "REPORT_DEFINITION_CONFLICT", "detail": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "REPORT_DEFINITION_INVALID", "detail": str(error)},
        ) from error
    return _report_definition_payload(definition)


@router.get(
    "/preview",
    response_model=ExportPreviewResponse,
    response_model_exclude_defaults=True,
    response_model_exclude_none=True,
)
def preview_exports(
    request: Request,
    form_id: str | None = None,
    employee_id: str | None = None,
    work_order_id: str | None = None,
    review_status: ReviewStatus | None = None,
    export_status: ExportStatus | None = None,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = get_current_actor(request, services)
    _require(actor, Permission.EXPORT_PREVIEW)
    preview = services.reporting.preview(
        FormFilters(
            form_id=form_id,
            employee_id=employee_id,
            work_order_id=work_order_id,
            review_status=review_status,
            export_status=export_status,
        ),
        actor.actor_id,
    )
    return _preview_payload(preview)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_export(
    body: ExportCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = get_current_actor(request, services)
    _require(actor, Permission.EXPORT_CREATE)
    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "IDEMPOTENCY_KEY_REQUIRED",
                "detail": "Idempotency-Key is required.",
            },
        )
    payload = body.model_dump(mode="json", exclude_none=True)
    try:
        task = services.tasks.submit(
            TaskCommand(
                "XLSX_EXPORT",
                "EXPORTS",
                actor.actor_id,
                idempotency_key,
                payload,
            )
        )
    except IdempotencyConflict as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_CONFLICT", "detail": str(error)},
        ) from error
    if task.status is TaskStatus.PENDING:
        background_tasks.add_task(_run_export_task_safely, services, task.task_id)
    return {
        "task_id": task.task_id,
        "status": task.status.value,
        "status_url": f"/api/v1/tasks/{task.task_id}",
        "events_url": f"/api/v1/tasks/{task.task_id}/events",
    }


def _run_export_task_safely(services: Services, task_id: str) -> None:
    """Run a persisted task without surfacing post-response failures."""
    try:
        services.export_handler.handle(task_id)
    except Exception:
        return


@router.get("/batches", response_model=list[ExportBatchResponse])
def list_export_batches(
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> list[dict[str, object]]:
    actor = get_current_actor(request, services)
    _require(actor, Permission.EXPORT_PREVIEW)
    return [_batch_payload(batch) for batch in services.reporting.list_batches()]


@router.get(
    "/batches/{batch_id}",
    response_model=ExportBatchResponse,
    response_model_exclude_none=True,
)
def get_export_batch(
    batch_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = get_current_actor(request, services)
    _require(actor, Permission.EXPORT_PREVIEW)
    batch = _require_batch(batch_id, services)
    return _batch_payload(batch)


@router.get("/batches/{batch_id}/download")
def download_export_batch(
    batch_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> Response:
    actor = get_current_actor(request, services)
    _require(actor, Permission.EXPORT_DOWNLOAD)
    batch = _require_batch(batch_id, services)
    root = services.settings.exports_root.resolve()
    path = Path(batch.file_path).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "EXPORT_PATH_INVALID",
                "detail": "Export file location is invalid.",
            },
        )
    if not path.is_file():
        raise HTTPException(
            status_code=410,
            detail={"code": "EXPORT_FILE_GONE", "detail": "Export file is unavailable."},
        )
    try:
        content = path.read_bytes()
    except OSError as error:
        raise HTTPException(
            status_code=410,
            detail={"code": "EXPORT_FILE_GONE", "detail": "Export file is unavailable."},
        ) from error
    if sha256(content).hexdigest() != batch.file_sha256:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "EXPORT_HASH_MISMATCH",
                "detail": "Export file failed integrity verification.",
            },
        )
    download_name = _safe_download_name(batch.download_name)
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


def _require_batch(batch_id: str, services: Services) -> ExportBatch:
    batch = services.repository.get_export_batch(batch_id)
    if batch is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "EXPORT_BATCH_NOT_FOUND", "detail": "Export batch was not found."},
        )
    return batch


def _report_definition_from_request(
    body: ReportDefinitionCreateRequest,
) -> ReportDefinition:
    return ReportDefinition(
        definition_id=body.definition_id,
        report_key=body.report_key,
        version=body.version,
        display_name=body.display_name,
        kind=body.kind,
        status=body.status,
        columns=tuple(ReportColumn(column.source_field, column.header) for column in body.columns),
        filters=tuple(body.filters),
        group_by=tuple(body.group_by),
        aggregates=tuple(
            ReportAggregate(aggregate.source_field, aggregate.operation, aggregate.header)
            for aggregate in body.aggregates
        ),
        sort_by=tuple(body.sort_by),
        worksheet=body.worksheet,
        fixed_template_key=body.fixed_template_key,
        fixed_template_sha256=body.fixed_template_sha256,
        fixed_cells=tuple(
            FixedCellMapping(item.cell, item.source_field) for item in body.fixed_cells
        ),
        fixed_table=(
            FixedTableMapping(
                body.fixed_table.start_row,
                body.fixed_table.max_rows,
                tuple(
                    FixedTableColumn(item.column, item.source_field)
                    for item in body.fixed_table.columns
                ),
            )
            if body.fixed_table is not None
            else None
        ),
    )


def _report_definition_payload(definition: ReportDefinition) -> dict[str, object]:
    return {
        "definition_id": definition.definition_id,
        "report_key": definition.report_key,
        "version": definition.version,
        "display_name": definition.display_name,
        "kind": definition.kind.value,
        "status": definition.status.value,
        "columns": [asdict(column) for column in definition.columns],
        "filters": list(definition.filters),
        "group_by": list(definition.group_by),
        "aggregates": [
            {
                "source_field": aggregate.source_field,
                "operation": aggregate.operation.value,
                "header": aggregate.header,
            }
            for aggregate in definition.aggregates
        ],
        "sort_by": list(definition.sort_by),
        "worksheet": definition.worksheet,
        "fixed_template_key": definition.fixed_template_key,
        "fixed_template_sha256": definition.fixed_template_sha256,
        "fixed_cells": [asdict(item) for item in definition.fixed_cells],
        "fixed_table": (
            {
                "start_row": definition.fixed_table.start_row,
                "max_rows": definition.fixed_table.max_rows,
                "columns": [asdict(item) for item in definition.fixed_table.columns],
            }
            if definition.fixed_table is not None
            else None
        ),
    }


def _batch_payload(batch: ExportBatch) -> dict[str, object]:
    return {
        "export_batch_id": batch.export_batch_id,
        "export_type": batch.export_type,
        "task_id": batch.task_id,
        "template_snapshot": thaw_json(batch.template_snapshot),
        "mapping_snapshot": thaw_json(batch.mapping_snapshot),
        "mapping_hash": batch.mapping_hash,
        "filters": thaw_json(batch.filters),
        "included_records": [
            {"form_id": form_id, "record_version": version}
            for form_id, version in batch.included_records
        ],
        "file_sha256": batch.file_sha256,
        "exported_by": batch.exported_by,
        "exported_at": batch.exported_at.isoformat(),
        "supersedes_batch_id": batch.supersedes_batch_id,
        "download_url": f"/api/v1/exports/batches/{batch.export_batch_id}/download",
        "download_name": _safe_download_name(batch.download_name),
    }


def _safe_download_name(name: str) -> str:
    candidate = Path(name).name
    if (
        candidate != name
        or re.fullmatch(r"[A-Za-z0-9_.-]+", candidate) is None
        or not candidate.lower().endswith(".xlsx")
    ):
        return "export.xlsx"
    return candidate


def _preview_payload(preview: ExportPreview) -> dict[str, object]:
    return {
        "included": [_preview_item_payload(item) for item in preview.included],
        "excluded": [_preview_item_payload(item) for item in preview.excluded],
        "mapping_snapshot": [asdict(mapping) for mapping in preview.mapping_snapshot],
    }


def _preview_item_payload(item: ExportPreviewItem) -> dict[str, object]:
    payload: dict[str, object] = {
        "form_id": item.form_id,
        "record_version": item.record_version,
    }
    if item.reason is not None:
        payload["reason"] = item.reason.value
    if item.reasons:
        reasons: list[dict[str, object]] = []
        for reason in item.reasons:
            reason_payload: dict[str, object] = {
                "scope": reason.scope.value,
                "code": reason.code,
                "message": reason.message,
            }
            if reason.field_key is not None:
                reason_payload["field_key"] = reason.field_key
            if reason.required is not None:
                reason_payload["required"] = reason.required
            if reason.allowed_values is not None:
                reason_payload["allowed_values"] = list(reason.allowed_values)
            if reason.minimum_value is not None:
                reason_payload["minimum_value"] = reason.minimum_value
            if reason.maximum_value is not None:
                reason_payload["maximum_value"] = reason.maximum_value
            reasons.append(reason_payload)
        payload["reasons"] = reasons
    return payload
