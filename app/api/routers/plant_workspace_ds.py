"""Factory-scoped plant manager Web adapter over the shared Bamboo domain."""

from datetime import UTC, datetime
from typing import Any, cast

from fastapi import APIRouter, Header, HTTPException, Query, Request, status

from app.api.routers.web_auth_ds import require_web_actor, require_web_csrf
from app.api.schemas.bamboo_process_ds import (
    CreatePersonnelTransferRequest,
    InspectionAppealDecisionRequest,
    PersonnelTransferDecisionRequest,
    SelectiveReturnRequest,
    TerminateInspectionRequest,
)
from app.api.schemas.managed_forms_ds import (
    ManagedFormListResponse,
    ManagedFormVersionResponse,
)
from app.api.schemas.web_workspaces_ds import OverviewCard, WorkspaceOverviewResponse
from app.application.bamboo_operations_ds import (
    BambooOperationError,
    BambooOperationsService,
)
from app.modules.bamboo_process.models_ds import BambooActor, BambooRole, BambooStage
from app.modules.electronic_forms.governance_ds import ManagedFormService
from app.modules.identity_access.web_policy_ds import (
    WebActor,
    WebWorkspace,
    allows_workspace,
    resolve_plant_factory,
)

router = APIRouter(prefix="/api/v1/plant", tags=["plant"])


def _plant_actor(
    request: Request,
    requested_factory_id: str | None = None,
) -> tuple[WebActor, str]:
    actor = require_web_actor(request)
    if not allows_workspace(actor, WebWorkspace.PLANT_MANAGER):
        raise HTTPException(
            status_code=403,
            detail={"code": "WEB_ROLE_FORBIDDEN", "detail": "当前账号不能进入厂长工作区。"},
        )
    try:
        plant_id = resolve_plant_factory(actor, requested_factory_id)
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail={"code": "CROSS_FACTORY_FORBIDDEN", "detail": str(error)},
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "FACTORY_REQUIRED", "detail": str(error)},
        ) from error
    return actor, plant_id


def _bamboo_actor(actor: WebActor, plant_id: str) -> BambooActor:
    return BambooActor(
        actor_id=actor.employee_code,
        employee_code=actor.employee_code,
        employee_name=actor.employee_name,
        factory_id=plant_id,
        factory_name=actor.factory_name,
        role=BambooRole.PLANT_MANAGER,
    )


def _bamboo(request: Request) -> BambooOperationsService:
    return cast(BambooOperationsService, request.app.state.services.bamboo_operations)


def _forms(request: Request) -> ManagedFormService:
    return ManagedFormService(request.app.state.services.engine)


def _operation_error(error: BambooOperationError) -> HTTPException:
    not_found = {
        "RECORD_NOT_VISIBLE",
        "NOTIFICATION_NOT_FOUND",
        "TRANSFER_NOT_FOUND",
        "INSPECTION_WINDOW_NOT_FOUND",
    }
    forbidden = {
        "MANAGER_REQUIRED",
        "RETURN_FORBIDDEN",
        "TRANSFER_VIEW_FORBIDDEN",
    }
    status_code = 404 if error.code in not_found else 403 if error.code in forbidden else 409
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "detail": str(error), **error.details},
    )


def _write_key(
    request: Request,
    csrf_token: str | None,
    idempotency_key: str | None,
) -> str:
    require_web_csrf(request, csrf_token)
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "detail": "缺少幂等键。"},
        )
    return idempotency_key.strip()


@router.get("/overview", response_model=WorkspaceOverviewResponse)
def overview(
    request: Request,
    factory_id: str | None = Query(default=None),
) -> WorkspaceOverviewResponse:
    actor, plant_id = _plant_actor(request, factory_id)
    bamboo_actor = _bamboo_actor(actor, plant_id)
    records = _bamboo(request).list_production_records(bamboo_actor)
    employees = _bamboo(request).list_factory_employees(bamboo_actor)
    inspections = _bamboo(request).list_inspection_queue(bamboo_actor)["items"]
    return WorkspaceOverviewResponse(
        workspace=WebWorkspace.PLANT_MANAGER.value,
        title="本厂概览",
        scope="FACTORY",
        factory_id=plant_id,
        factory_name=actor.factory_name if plant_id == actor.factory_id else "",
        cards=[
            OverviewCard(key="production", label="生产记录", value=len(records)),
            OverviewCard(key="employees", label="本厂员工", value=len(employees)),
            OverviewCard(key="inspections", label="检测队列", value=len(inspections)),
        ],
    )


@router.get("/forms", response_model=ManagedFormListResponse)
def forms(request: Request) -> ManagedFormListResponse:
    _, plant_id = _plant_actor(request)
    return ManagedFormListResponse(
        items=[
            ManagedFormVersionResponse.model_validate(item)
            for item in _forms(request).list_plant_forms(plant_id)
        ]
    )


@router.get("/workflows")
def workflows(request: Request) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    return {
        "items": _bamboo(request).workflow_stage_summaries(
            _bamboo_actor(actor, plant_id)
        )
    }


@router.get("/production")
def production(request: Request) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    records = _bamboo(request).list_production_records(_bamboo_actor(actor, plant_id))
    return {
        "overview": {
            "total": len(records),
            "active": sum(item["status"] == "ACTIVE" for item in records),
            "completed": sum(item["status"] == "COMPLETED" for item in records),
        },
        "records": records,
    }


@router.get("/production/{record_id}")
def production_detail(record_id: str, request: Request) -> dict[str, Any]:
    actor, plant_id = _plant_actor(request)
    try:
        return _bamboo(request).production_record_detail(
            record_id,
            _bamboo_actor(actor, plant_id),
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/records/{record_id}/return")
def return_bamboo_record(
    record_id: str,
    body: SelectiveReturnRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    key = _write_key(request, x_csrf_token, idempotency_key)
    try:
        stages = [BambooStage(value) for value in body.target_stages]
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_RETURN_STAGES", "detail": "打回环节无效。"},
        ) from error
    try:
        return _bamboo(request).selective_return(
            record_id,
            actor=_bamboo_actor(actor, plant_id),
            target_stages=stages,
            reason=body.reason,
            source="PLANT_MANAGER",
            expected_revision=body.expected_revision,
            idempotency_key=key,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/exceptions")
def exceptions(
    request: Request,
    bucket: str = Query(default="active"),
    q: str = Query(default=""),
) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    try:
        return _bamboo(request).list_inspection_queue(
            _bamboo_actor(actor, plant_id),
            bucket=bucket,
            query=q,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/inspection-queue/{record_id}/terminate")
def terminate_inspection(
    record_id: str,
    body: TerminateInspectionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    _write_key(request, x_csrf_token, idempotency_key)
    try:
        return _bamboo(request).terminate_inspection(
            record_id,
            actor=_bamboo_actor(actor, plant_id),
            confirm=body.confirm,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/inspection-queue/{record_id}/appeal/decision")
def decide_inspection_appeal(
    record_id: str,
    body: InspectionAppealDecisionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    _write_key(request, x_csrf_token, idempotency_key)
    try:
        return _bamboo(request).decide_inspection_appeal(
            record_id,
            actor=_bamboo_actor(actor, plant_id),
            approve=body.approve,
            note=body.note,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/employees")
def employees(request: Request) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    return {
        "items": _bamboo(request).list_factory_employees(
            _bamboo_actor(actor, plant_id)
        )
    }


@router.get("/role-options")
def role_options(request: Request) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    return {
        "items": _bamboo(request).list_role_options(_bamboo_actor(actor, plant_id))
    }


@router.get("/personnel-transfers")
def personnel_transfers(request: Request) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    return {
        "items": _bamboo(request).list_personnel_transfers(
            _bamboo_actor(actor, plant_id)
        )
    }


@router.post("/personnel-transfers", status_code=status.HTTP_201_CREATED)
def create_personnel_transfer(
    body: CreatePersonnelTransferRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    _write_key(request, x_csrf_token, idempotency_key)
    try:
        return _bamboo(request).create_personnel_transfer(
            actor=_bamboo_actor(actor, plant_id),
            employee_code=body.employee_code,
            to_role=body.to_role,
            target_factory_id=body.target_factory_id,
            reason=body.reason,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.post("/personnel-transfers/{transfer_id}/manager-decision")
def decide_personnel_transfer(
    transfer_id: str,
    body: PersonnelTransferDecisionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    _write_key(request, x_csrf_token, idempotency_key)
    try:
        return _bamboo(request).decide_personnel_transfer_as_manager(
            transfer_id,
            actor=_bamboo_actor(actor, plant_id),
            approve=body.approve,
            note=body.note,
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error


@router.get("/payroll")
def payroll(
    request: Request,
    month: str = Query(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m")),
) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    return _bamboo(request).monthly_summary(_bamboo_actor(actor, plant_id), month)


@router.get("/notifications")
def notifications(request: Request) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    return _bamboo(request).list_notifications(_bamboo_actor(actor, plant_id))


@router.post("/notifications/{notification_id}/acknowledge")
def acknowledge_notification(
    notification_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor, plant_id = _plant_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _bamboo(request).read_notification(
            notification_id,
            actor=_bamboo_actor(actor, plant_id),
        )
    except BambooOperationError as error:
        raise _operation_error(error) from error
