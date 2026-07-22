"""Authenticated, factory-scoped bamboo workflow routes."""

from typing import cast

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.routers.mobile_auth_ds import require_csrf, require_mobile_actor
from app.api.schemas.bamboo_process_ds import (
    BambooDashboardResponse,
    BambooRecordResponse,
    BambooSubmissionResponse,
    BambooTaskListResponse,
    CreateBambooRecordRequest,
    SubmitBambooStageRequest,
)
from app.application.mobile_identity_ds import MobileActor
from app.modules.bamboo_process.errors_ds import (
    BambooPermissionDenied,
    BambooRecordNotFound,
    StaleBambooRevision,
)
from app.modules.bamboo_process.models_ds import (
    BambooActor,
    BambooRecord,
    BambooRole,
    BambooStage,
    TaskBucket,
)
from app.services.container import Services

router = APIRouter(prefix="/bamboo")


def _services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


def _bamboo_actor(request: Request) -> BambooActor:
    mobile_actor = require_mobile_actor(request)
    if not mobile_actor.factory_id or not mobile_actor.bamboo_role:
        raise HTTPException(
            status_code=403,
            detail={"code": "BAMBOO_ROLE_REQUIRED", "detail": "当前账号未分配竹丝工序职务。"},
        )
    try:
        role = BambooRole(mobile_actor.bamboo_role)
    except ValueError as error:
        raise HTTPException(
            status_code=403,
            detail={"code": "BAMBOO_ROLE_REQUIRED", "detail": "当前竹丝工序职务无效。"},
        ) from error
    return _domain_actor(mobile_actor, role)


def _domain_actor(actor: MobileActor, role: BambooRole) -> BambooActor:
    return BambooActor(
        actor_id=actor.user_id,
        employee_code=actor.employee_code,
        employee_name=actor.employee_name,
        factory_id=actor.factory_id,
        factory_name=actor.factory_name,
        role=role,
    )


def _require_write_headers(
    request: Request,
    idempotency_key: str | None,
    csrf_token: str | None,
) -> str:
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "detail": "缺少幂等键。"},
        )
    require_csrf(request, csrf_token)
    return idempotency_key.strip()


@router.get("/dashboard", response_model=BambooDashboardResponse)
def dashboard(request: Request) -> BambooDashboardResponse:
    actor = _bamboo_actor(request)
    service = _services(request).bamboo_process
    return BambooDashboardResponse(
        available=len(service.list_tasks(actor=actor, bucket=TaskBucket.AVAILABLE)),
        waiting=len(service.list_tasks(actor=actor, bucket=TaskBucket.WAITING)),
        completed=len(service.list_tasks(actor=actor, bucket=TaskBucket.COMPLETED)),
    )


@router.get("/tasks", response_model=BambooTaskListResponse)
def list_tasks(
    request: Request,
    bucket: TaskBucket = TaskBucket.AVAILABLE,
) -> BambooTaskListResponse:
    actor = _bamboo_actor(request)
    records = _services(request).bamboo_process.list_tasks(actor=actor, bucket=bucket)
    return BambooTaskListResponse(
        bucket=bucket.value,
        tasks=[_response(record) for record in records],
    )


@router.post(
    "/records",
    response_model=BambooRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_record(
    body: CreateBambooRecordRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> BambooRecordResponse:
    actor = _bamboo_actor(request)
    key = _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        record = _services(request).bamboo_process.create_record(
            actor=actor,
            base_info=dict(body.base_info),
            source_type="MOBILE_CREATED",
            source_ref=key,
        )
    except BambooPermissionDenied as error:
        raise HTTPException(
            status_code=403,
            detail={"code": "BAMBOO_ROLE_REQUIRED", "detail": str(error)},
        ) from error
    return _response(record)


@router.get("/records/{record_id}", response_model=BambooRecordResponse)
def get_record(record_id: str, request: Request) -> BambooRecordResponse:
    actor = _bamboo_actor(request)
    record = _services(request).bamboo_process.get_visible(record_id, actor=actor)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "RECORD_NOT_VISIBLE", "detail": "记录不存在或当前不可见。"},
        )
    return _response(record)


@router.post(
    "/records/{record_id}/stages/{stage_key}/submit",
    response_model=BambooRecordResponse,
)
def submit_stage(
    record_id: str,
    stage_key: BambooStage,
    body: SubmitBambooStageRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> BambooRecordResponse:
    actor = _bamboo_actor(request)
    key = _require_write_headers(request, idempotency_key, x_csrf_token)
    service = _services(request).bamboo_process
    if service.get_visible(record_id, actor=actor) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "RECORD_NOT_VISIBLE", "detail": "记录不存在或当前不可见。"},
        )
    try:
        record = service.submit_stage(
            record_id,
            actor=actor,
            stage=stage_key,
            values=dict(body.values),
            expected_revision=body.expected_revision,
            idempotency_key=key,
            device_id=body.device_id,
            request_id=str(getattr(request.state, "request_id", "unknown")),
        )
    except StaleBambooRevision as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "STALE_REVISION",
                "detail": str(error),
                "expected_revision": error.expected,
                "actual_revision": error.actual,
            },
        ) from error
    except BambooPermissionDenied as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "STAGE_NOT_AVAILABLE", "detail": str(error)},
        ) from error
    except BambooRecordNotFound as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "RECORD_NOT_VISIBLE", "detail": str(error)},
        ) from error
    return _response(record)


def _response(record: BambooRecord) -> BambooRecordResponse:
    return BambooRecordResponse(
        record_id=record.record_id,
        display_no=record.display_no,
        factory_id=record.factory_id,
        source_type=record.source_type,
        source_ref=record.source_ref,
        base_info=record.base_info,
        current_stage=(record.current_stage.value if record.current_stage else None),
        status=record.status.value,
        revision=record.revision,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        submissions=[
            BambooSubmissionResponse(
                submission_id=submission.submission_id,
                stage=submission.stage.value,
                version=submission.version,
                values=submission.values,
                actor_id=submission.actor_id,
                actor_name=submission.actor_name,
                role_code=submission.role_code,
                submitted_at=submission.submitted_at,
            )
            for submission in record.submissions
            if not submission.invalidated
        ],
    )
