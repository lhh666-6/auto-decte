"""Authenticated, factory-scoped bamboo workflow routes."""

import hashlib
import json as _json
from decimal import Decimal
from io import BytesIO
from typing import Annotated, cast
from urllib.parse import quote

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from openpyxl import Workbook

from app.api.routers.mobile_auth_ds import require_csrf, require_mobile_actor
from app.api.schemas.bamboo_process_ds import (
    BambooDashboardResponse,
    BambooRecordOptionsResponse,
    BambooRecordResponse,
    BambooSubmissionResponse,
    BambooTaskListResponse,
    BambooUpstreamRecordResponse,
    CreateBambooRecordRequest,
    CreateFactoryEmployeeRequest,
    CreateFactoryRequest,
    CreateInspectionRequest,
    CreatePersonnelTransferRequest,
    EmployeeRoleAssignmentRequest,
    FinanceDecisionRequest,
    FinanceInquiryReplyRequest,
    FinanceInquiryRequest,
    InspectionAppealDecisionRequest,
    PayrollRuleRequest,
    PersonnelTransferDecisionRequest,
    RoleChangeDecisionRequest,
    RoleChangeRequest,
    SubmitBambooStageRequest,
    SubmitInspectionAppealRequest,
    TerminateInspectionRequest,
)
from app.application.bamboo_operations_ds import BambooOperationError
from app.application.mobile_identity_ds import MobileActor
from app.modules.bamboo_process.errors_ds import (
    BambooIdempotencyConflict,
    BambooPermissionDenied,
    BambooRecordNotFound,
    StaleBambooRevision,
)
from app.modules.bamboo_process.facade_ds import InspectionContext
from app.modules.bamboo_process.models_ds import (
    BambooActor,
    BambooFormType,
    BambooRecord,
    BambooRole,
    BambooStage,
    StageSubmission,
    TaskBucket,
)
from app.modules.bamboo_process.ports_ds import (
    BambooCageOccupied,
    BambooRepositoryConflict,
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
    if role is BambooRole.PLANT_MANAGER:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "PLANT_MANAGER_WEB_ONLY",
                "detail": "厂长业务请使用 Web 工作区。",
            },
        )
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
    if actor.role is BambooRole.INSPECTOR:
        try:
            counts = _services(request).bamboo_operations.get_dashboard(actor)
        except BambooOperationError as error:
            raise _operation_error(error) from error
        return BambooDashboardResponse(
            available=counts["available"],
            waiting=counts["waiting"],
            completed=counts["completed"],
        )
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
    cage_no: str | None = None,
) -> BambooTaskListResponse:
    actor = _bamboo_actor(request)
    service = _services(request).bamboo_process
    inspection_context: InspectionContext | None = None
    if actor.role is BambooRole.INSPECTOR:
        inspection_context = _services(request).bamboo_operations.build_inspection_context(actor)
    records = service.list_tasks(
        actor=actor,
        bucket=bucket,
        cage_no=cage_no,
        inspection_context=inspection_context,
    )
    return BambooTaskListResponse(
        bucket=bucket.value,
        tasks=[
            _response(
                record,
                actor=actor,
                upstream_record=service.get_upstream(record, actor=actor),
            )
            for record in records
        ],
    )


@router.get("/record-options", response_model=BambooRecordOptionsResponse)
def record_options(request: Request) -> BambooRecordOptionsResponse:
    actor = _bamboo_actor(request)
    try:
        options = _services(request).bamboo_operations.record_options(actor)
    except BambooOperationError as error:
        raise _operation_error(error) from error
    return BambooRecordOptionsResponse(**options)


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
    services = _services(request)
    # Validate base_info first so the canonical payload hash is computed from
    # server-normalised values, not from the raw JSON body.
    try:
        base_info = services.bamboo_operations.validate_record_base_info(
            actor,
            dict(body.base_info),
        )
    except BambooOperationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "detail": str(error)},
        ) from error
    # Compute canonical payload hash for idempotency binding.
    # Only include client-supplied fields so that server-injected data
    # (options_version, net_weight) changing across preset updates does
    # not cause false IDEMPOTENCY_CONFLICT on replay.
    _CLIENT_BASE_INFO_KEYS = frozenset({
        "mode", "special_classes", "length", "shade", "grade",
        "supplier", "cage_no", "bundle_count",
    })
    form_type = BambooFormType(body.form_type)
    create_payload = {
        "actor_id": actor.actor_id,
        "form_type": form_type.value,
        "base_info": {
            key: value
            for key, value in base_info.items()
            if key in _CLIENT_BASE_INFO_KEYS
        },
    }
    canonical = _json.dumps(
        create_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode()
    create_payload_hash = hashlib.sha256(canonical).hexdigest()

    try:
        repeated = services.bamboo_repository.find_created_result(
            actor.actor_id, key, payload_hash=create_payload_hash
        )
        if repeated is not None:
            return _response(repeated, actor=actor)
        record = services.bamboo_process.create_record(
            actor=actor,
            base_info=base_info,
            source_type="MOBILE_CREATED",
            source_ref=key,
            form_type=form_type,
            create_payload_hash=create_payload_hash,
        )
    except BambooIdempotencyConflict as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "IDEMPOTENCY_CONFLICT",
                "detail": "该幂等键已用于不同的请求，请刷新后重新提交。",
            },
        ) from error
    except BambooPermissionDenied as error:
        raise HTTPException(
            status_code=403,
            detail={"code": "BAMBOO_ROLE_REQUIRED", "detail": str(error)},
        ) from error
    except BambooOperationError as error:
        status_code_ = 422 if error.code == "INVALID_BAMBOO_BASE_INFO" else 409
        raise HTTPException(
            status_code=status_code_,
            detail={"code": error.code, "detail": str(error)},
        ) from error
    except BambooCageOccupied as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "CAGE_ALREADY_IN_USE",
                "detail": "该笼号仍在未完成流程中。",
                "cage_no": error.cage_no,
                "sorting_record_id": error.sorting_record_id,
            },
        ) from error
    except BambooRepositoryConflict as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "BAMBOO_RECORD_CONFLICT", "detail": str(error)},
        ) from error
    return _response(record, actor=actor)


def _operation_error(error: BambooOperationError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": error.code, "detail": str(error), **error.details},
    )


@router.get("/payroll-rules")
def list_payroll_rules(request: Request) -> list[dict[str, object]]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_payroll_rules(actor)
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/payroll-rules", status_code=status.HTTP_201_CREATED)
def create_payroll_rule(
    body: PayrollRuleRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.create_payroll_rule(
            actor=actor,
            rule_key=body.rule_key,
            configuration=body.configuration,
            system_default=body.system_default,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/admin/assignments", status_code=status.HTTP_201_CREATED)
def assign_employee_role(
    body: EmployeeRoleAssignmentRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.assign_employee_role(
            actor=actor,
            employee_code=body.employee_code,
            role_code=body.role_code,
            factory_id=body.factory_id,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/role-options")
def role_options(request: Request) -> list[dict[str, object]]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_role_options(actor)
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/admin/employees")
def list_factory_employees(request: Request) -> list[dict[str, object]]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_factory_employees(actor)
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/factories")
def list_factories(request: Request) -> list[dict[str, object]]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_factories(actor)
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/admin/employees", status_code=status.HTTP_201_CREATED)
def create_factory_employee(
    body: CreateFactoryEmployeeRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.create_factory_employee(
            actor=actor,
            employee_name=body.employee_name,
            initial_pin=body.initial_pin,
            role_code=body.role_code,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/history")
def actor_history(request: Request) -> list[dict[str, object]]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_actor_history(actor)
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/admin/factories", status_code=status.HTTP_201_CREATED)
def create_factory(
    body: CreateFactoryRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.create_factory(
            actor=actor, code=body.code, name=body.name
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/records/{record_id}/operations")
def record_operations(record_id: str, request: Request) -> dict[str, object]:
    actor = _bamboo_actor(request)
    services = _services(request)
    if services.bamboo_process.get_visible(record_id, actor=actor) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "RECORD_NOT_VISIBLE", "detail": "记录不存在或当前不可见。"},
        )
    try:
        return services.bamboo_operations.record_summary(record_id, actor)
    except BambooOperationError as error:
        if error.code == "RECORD_NOT_VISIBLE":
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "RECORD_NOT_VISIBLE",
                    "detail": "记录不存在或当前不可见。",
                },
            ) from error
        raise _operation_error(error) from error


@router.get("/inspection-queue")
def inspection_queue(
    request: Request,
    bucket: str = "active",
    q: str = "",
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_inspection_queue(
            actor, bucket=bucket, query=q
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/inspection-queue/{record_id}/claim")
def claim_inspection(
    record_id: str,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    key = _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.claim_inspection(
            record_id, actor=actor, idempotency_key=key
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/inspection-queue/{record_id}/terminate")
def terminate_inspection(
    record_id: str,
    body: TerminateInspectionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.terminate_inspection(
            record_id, actor=actor, confirm=body.confirm,
            idempotency_key=(idempotency_key or "").strip(),
            reason=body.reason,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/inspection-queue/{record_id}/appeal/claim")
def claim_inspection_appeal(
    record_id: str,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.claim_inspection_appeal(
            record_id, actor=actor
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/inspection-queue/{record_id}/appeal")
def submit_inspection_appeal(
    record_id: str,
    body: SubmitInspectionAppealRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        stage = BambooStage(body.target_stage)
        return _services(request).bamboo_operations.submit_inspection_appeal(
            record_id,
            actor=actor,
            target_stage=stage,
            text_evidence=body.text_evidence,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_INSPECTION_STAGE", "detail": "无效的申诉环节"},
        ) from error
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/inspection-queue/{record_id}/appeal/decision")
def decide_inspection_appeal(
    record_id: str,
    body: InspectionAppealDecisionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.decide_inspection_appeal(
            record_id,
            actor=actor,
            approve=body.approve,
            note=body.note,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/notifications")
def list_notifications(request: Request) -> dict[str, object]:
    actor = _bamboo_actor(request)
    return _services(request).bamboo_operations.list_notifications(actor)


@router.post("/notifications/{notification_id}/read")
def read_notification(
    notification_id: str,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.read_notification(
            notification_id, actor=actor
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/records/{record_id}/inspections", status_code=status.HTTP_201_CREATED)
def create_inspection(
    record_id: str,
    body: CreateInspectionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    key = _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        target_stage = BambooStage(body.target_stage) if body.target_stage else None
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_INSPECTION_STAGE", "detail": "无效的检测流程"},
        ) from error
    try:
        return _services(request).bamboo_operations.create_inspection(
            record_id,
            actor=actor,
            serial_no=body.serial_no,
            target_stage=target_stage,
            moisture_points=[Decimal(str(value)) for value in body.moisture_points],
            conclusion=body.conclusion,
            note=body.note,
            text_evidence=body.text_evidence,
            device_id=body.device_id,
            request_id=str(getattr(request.state, "request_id", "unknown")),
            idempotency_key=key,
            has_file_evidence=False,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post(
    "/records/{record_id}/inspection-submit",
    status_code=status.HTTP_201_CREATED,
)
async def submit_inspection_with_evidence(
    record_id: str,
    request: Request,
    conclusion: Annotated[str, Form()],
    device_id: Annotated[str, Form()],
    target_stage: Annotated[str | None, Form()] = None,
    text_evidence: Annotated[str | None, Form()] = None,
    moisture_points_json: Annotated[str | None, Form()] = None,
    photos: Annotated[list[UploadFile] | None, File()] = None,
    audio: Annotated[UploadFile | None, File()] = None,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    key = _require_write_headers(request, idempotency_key, x_csrf_token)
    uploads = [*(photos or []), *([audio] if audio else [])]
    contents: list[tuple[UploadFile, bytes]] = []
    for upload in uploads:
        content = await upload.read()
        if not content or len(content) > 20 * 1024 * 1024:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_EVIDENCE_SIZE", "detail": "留痕文件必须小于 20MB"},
            )
        contents.append((upload, content))
    moisture_points: list[Decimal] = []
    if moisture_points_json:
        try:
            raw_points = _json.loads(moisture_points_json)
            if not isinstance(raw_points, list):
                raise ValueError("must be a JSON array")
            moisture_points = [Decimal(str(value)) for value in raw_points]
        except (ValueError, _json.JSONDecodeError) as error:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_MOISTURE_POINTS",
                    "detail": "含水率检测点必须是 JSON 数字数组。",
                },
            ) from error
        if len(moisture_points) > 20:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_MOISTURE_POINTS",
                    "detail": "含水率检测点数量不能超过 20 个。",
                },
            )
    try:
        stage = BambooStage(target_stage) if target_stage else None
        created = _services(request).bamboo_operations.create_inspection(
            record_id,
            actor=actor,
            serial_no=None,
            target_stage=stage,
            moisture_points=moisture_points,
            conclusion=conclusion,
            note=text_evidence,
            text_evidence=text_evidence,
            device_id=device_id,
            request_id=str(getattr(request.state, "request_id", "unknown")),
            idempotency_key=key,
            has_file_evidence=bool(contents),
        )
        for upload, content in contents:
            created.setdefault("evidence", []).append(
                _services(request).bamboo_operations.add_file_evidence(
                    str(created["inspection_id"]),
                    actor=actor,
                    evidence_type=(
                        "AUDIO"
                        if (upload.content_type or "").startswith("audio/")
                        else "PHOTO"
                    ),
                    content=content,
                    filename=upload.filename or "evidence.bin",
                    mime_type=upload.content_type or "application/octet-stream",
                )
            )
        return created
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_INSPECTION_STAGE", "detail": "无效的检测流程"},
        ) from error
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/inspections/{inspection_id}/evidence", status_code=status.HTTP_201_CREATED)
async def upload_inspection_evidence(
    inspection_id: str,
    request: Request,
    evidence_type: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    content = await file.read()
    try:
        return _services(request).bamboo_operations.add_file_evidence(
            inspection_id,
            actor=actor,
            evidence_type=evidence_type,
            content=content,
            filename=file.filename or "evidence.bin",
            mime_type=file.content_type or "application/octet-stream",
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


# V1 Final Truth Closure §11-12: close_exception and selective_return routes REMOVED.
# Exception closure is now handled by QualityDispositionService transaction.
# Production rewind is not a V1 capability.


@router.post("/role-change-requests", status_code=status.HTTP_201_CREATED)
def request_role_change(
    body: RoleChangeRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.request_role_change(
            actor=actor, to_role=body.to_role, reason=body.reason
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/personnel-transfers", status_code=status.HTTP_201_CREATED)
def create_personnel_transfer(
    body: CreatePersonnelTransferRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.create_personnel_transfer(
            actor=actor,
            employee_code=body.employee_code,
            to_role=body.to_role,
            target_factory_id=body.target_factory_id,
            reason=body.reason,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/personnel-transfers")
def list_personnel_transfers(request: Request) -> list[dict[str, object]]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_personnel_transfers(actor)
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/personnel-transfers/{transfer_id}/manager-decision")
def decide_personnel_transfer_as_manager(
    transfer_id: str,
    body: PersonnelTransferDecisionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.decide_personnel_transfer_as_manager(
            transfer_id,
            actor=actor,
            approve=body.approve,
            note=body.note,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/personnel-transfers/{transfer_id}/execute")
def execute_personnel_transfer(
    transfer_id: str,
    body: PersonnelTransferDecisionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.execute_personnel_transfer(
            transfer_id,
            actor=actor,
            approve=body.approve,
            note=body.note,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/role-change-requests")
def list_role_changes(request: Request) -> list[dict[str, object]]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_role_changes(actor)
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/role-change-requests/{role_request_id}/decision")
def decide_role_change(
    role_request_id: str,
    body: RoleChangeDecisionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.decide_role_change(
            role_request_id, actor=actor, approve=body.approve, note=body.note
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/finance/daily-batches")
def list_daily_batches(request: Request) -> list[dict[str, object]]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_daily_batches(actor)
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/finance/items/{item_id}/decision")
def decide_finance_item(
    item_id: str,
    body: FinanceDecisionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.decide_daily_item(
            item_id, actor=actor, decision=body.decision, note=body.note
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/finance/items/{item_id}/inquiries", status_code=status.HTTP_201_CREATED)
def create_finance_inquiry(
    item_id: str,
    body: FinanceInquiryRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.create_inquiry(
            item_id, actor=actor, subject=body.subject, body=body.body
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/finance/inquiries/{inquiry_id}/reply")
def reply_finance_inquiry(
    inquiry_id: str,
    body: FinanceInquiryReplyRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.reply_inquiry(
            inquiry_id, actor=actor, body=body.body, close=body.close
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/finance/inquiries")
def list_finance_inquiries(request: Request) -> list[dict[str, object]]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_inquiries(actor)
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/finance/monthly-summary")
def finance_monthly_summary(month: str, request: Request) -> dict[str, object]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.monthly_summary(actor, month)
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/finance/export.xlsx")
def export_finance_xlsx(
    request: Request,
    month: str | None = None,
) -> StreamingResponse:
    actor = _bamboo_actor(request)
    try:
        if month:
            summary = _services(request).bamboo_operations.monthly_summary(actor, month)
            rows = [[item["employee_code"], item["amount"]] for item in summary["items"]]
            title = f"竹丝工资月汇总-{month}"
            headers = ["工号", "已审批工资"]
        else:
            batches = _services(request).bamboo_operations.list_daily_batches(actor)
            rows = [
                [
                    batch["business_date"],
                    item["employee_code"],
                    item["amount"],
                    item["status"],
                    item["record_id"],
                ]
                for batch in batches
                for item in batch["items"]
            ]
            title = "竹丝工资单日审计明细"
            headers = ["日期", "工号", "金额", "财务状态", "原始表单ID"]
    except BambooOperationError as error:
        raise _operation_error(error) from error
    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:  # pragma: no cover - a new workbook always has one sheet
        raise RuntimeError("XLSX workbook did not create an active sheet")
    sheet.title = "工资审计"
    sheet.append(headers)
    for row in rows:
        sheet.append(row)
    stream = BytesIO()
    workbook.save(stream)
    stream.seek(0)
    filename = f"{title}.xlsx"
    return StreamingResponse(
        stream,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.get("/records/{record_id}", response_model=BambooRecordResponse)
def get_record(record_id: str, request: Request) -> BambooRecordResponse:
    actor = _bamboo_actor(request)
    service = _services(request).bamboo_process
    record = service.get_visible(record_id, actor=actor)
    if record is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "RECORD_NOT_VISIBLE", "detail": "记录不存在或当前不可见。"},
        )
    return _response(
        record,
        actor=actor,
        upstream_record=service.get_upstream(record, actor=actor),
    )


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
        values = _services(request).bamboo_operations.validate_stage_values(
            stage_key,
            dict(body.values),
        )
        record = service.submit_stage(
            record_id,
            actor=actor,
            stage=stage_key,
            values=values,
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
    except BambooIdempotencyConflict as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "IDEMPOTENCY_CONFLICT",
                "detail": "该幂等键已用于不同的请求，请刷新后重新提交。",
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
    except BambooOperationError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "detail": str(error)},
        ) from error
    except BambooRepositoryConflict as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "BAMBOO_RECORD_CONFLICT", "detail": str(error)},
        ) from error
    return _response(
        record,
        actor=actor,
        upstream_record=service.get_upstream(record, actor=actor),
    )


def _submission_response(
    submission: StageSubmission,
    actor: BambooActor,
) -> BambooSubmissionResponse:
    values = dict(submission.values)
    if (
        actor.role
        not in {
            BambooRole.PLANT_MANAGER,
            BambooRole.FINANCE_APPROVER,
            BambooRole.SYSTEM_ADMIN,
        }
        and submission.actor_id != actor.actor_id
    ):
        values.pop("wage_amount", None)
    return BambooSubmissionResponse(
        submission_id=submission.submission_id,
        stage=submission.stage.value,
        version=submission.version,
        values=values,
        actor_id=submission.actor_id,
        actor_name=submission.actor_name,
        role_code=submission.role_code,
        submitted_at=submission.submitted_at,
    )


def _upstream_response(
    record: BambooRecord,
    actor: BambooActor,
) -> BambooUpstreamRecordResponse:
    return BambooUpstreamRecordResponse(
        record_id=record.record_id,
        display_no=record.display_no,
        factory_id=record.factory_id,
        form_type=record.form_type.value,
        base_info=record.base_info,
        current_stage=record.current_stage.value if record.current_stage else None,
        status=record.status.value,
        revision=record.revision,
        submissions=[
            _submission_response(submission, actor)
            for submission in record.submissions
            if not submission.invalidated
        ],
    )


def _response(
    record: BambooRecord,
    *,
    actor: BambooActor,
    upstream_record: BambooRecord | None = None,
) -> BambooRecordResponse:
    return BambooRecordResponse(
        record_id=record.record_id,
        display_no=record.display_no,
        factory_id=record.factory_id,
        source_type=record.source_type,
        source_ref=record.source_ref,
        form_type=record.form_type.value,
        production_object_id=record.production_object_id,
        source_record_id=record.source_record_id,
        source_snapshot=record.source_snapshot,
        base_info=record.base_info,
        current_stage=(record.current_stage.value if record.current_stage else None),
        status=record.status.value,
        revision=record.revision,
        created_by=record.created_by,
        created_at=record.created_at,
        updated_at=record.updated_at,
        submissions=[
            _submission_response(submission, actor)
            for submission in record.submissions
            if not submission.invalidated
        ],
        upstream_record=(
            _upstream_response(upstream_record, actor)
            if upstream_record is not None
            else None
        ),
    )
