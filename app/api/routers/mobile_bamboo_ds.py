"""Authenticated, factory-scoped bamboo workflow routes."""

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
    CloseInspectionExceptionRequest,
    CreateBambooRecordRequest,
    CreateFactoryEmployeeRequest,
    CreateFactoryRequest,
    CreateInspectionRequest,
    EmployeeRoleAssignmentRequest,
    FinanceDecisionRequest,
    FinanceInquiryReplyRequest,
    FinanceInquiryRequest,
    PayrollRuleRequest,
    RoleChangeDecisionRequest,
    RoleChangeRequest,
    SelectiveReturnRequest,
    SubmitBambooStageRequest,
)
from app.application.bamboo_operations_ds import BambooOperationError
from app.application.mobile_identity_ds import MobileActor
from app.modules.bamboo_process.errors_ds import (
    BambooPermissionDenied,
    BambooRecordNotFound,
    StaleBambooRevision,
)
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
    cage_no: str | None = None,
) -> BambooTaskListResponse:
    actor = _bamboo_actor(request)
    service = _services(request).bamboo_process
    records = service.list_tasks(
        actor=actor,
        bucket=bucket,
        cage_no=cage_no,
    )
    return BambooTaskListResponse(
        bucket=bucket.value,
        tasks=[
            _response(
                record,
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
    repeated = services.bamboo_repository.find_created_result(actor.actor_id, key)
    if repeated is not None:
        return _response(repeated)
    try:
        base_info = services.bamboo_operations.validate_record_base_info(
            actor,
            dict(body.base_info),
        )
        record = services.bamboo_process.create_record(
            actor=actor,
            base_info=base_info,
            source_type="MOBILE_CREATED",
            source_ref=key,
            form_type=BambooFormType(body.form_type),
        )
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
    return _response(record)


def _operation_error(error: BambooOperationError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": error.code, "detail": str(error)},
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
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    try:
        return _services(request).bamboo_operations.list_inspection_queue(
            actor, bucket=bucket
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
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.claim_inspection(record_id, actor=actor)
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
        )
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


@router.post("/inspection-exceptions/{exception_id}/close")
def close_inspection_exception(
    exception_id: str,
    body: CloseInspectionExceptionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        return _services(request).bamboo_operations.close_exception(
            exception_id, actor=actor, resolution=body.resolution
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/records/{record_id}/return")
def selective_return(
    record_id: str,
    body: SelectiveReturnRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _bamboo_actor(request)
    _require_write_headers(request, idempotency_key, x_csrf_token)
    try:
        stages = [BambooStage(value) for value in body.target_stages]
        return _services(request).bamboo_operations.selective_return(
            record_id,
            actor=actor,
            target_stages=stages,
            reason=body.reason,
            source=body.source,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_RETURN_STAGES", "detail": "无效的回退流程"},
        ) from error
    except BambooOperationError as error:
        raise _operation_error(error) from error


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
        upstream_record=service.get_upstream(record, actor=actor),
    )


def _submission_response(submission: StageSubmission) -> BambooSubmissionResponse:
    return BambooSubmissionResponse(
        submission_id=submission.submission_id,
        stage=submission.stage.value,
        version=submission.version,
        values=submission.values,
        actor_id=submission.actor_id,
        actor_name=submission.actor_name,
        role_code=submission.role_code,
        submitted_at=submission.submitted_at,
    )


def _upstream_response(record: BambooRecord) -> BambooUpstreamRecordResponse:
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
            _submission_response(submission)
            for submission in record.submissions
            if not submission.invalidated
        ],
    )


def _response(
    record: BambooRecord,
    *,
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
            _submission_response(submission)
            for submission in record.submissions
            if not submission.invalidated
        ],
        upstream_record=(
            _upstream_response(upstream_record) if upstream_record is not None else None
        ),
    )
