"""Phase 1 factory-scoped plant manager workspace endpoints."""

from fastapi import APIRouter, Header, HTTPException, Query, Request

from app.api.routers.web_auth_ds import require_web_actor, require_web_csrf
from app.api.schemas.managed_forms_ds import (
    ManagedFormListResponse,
    ManagedFormVersionResponse,
    ManagementNotificationListResponse,
    ManagementNotificationResponse,
)
from app.api.schemas.submission_ledger_ds import ReturnSubmissionRequest
from app.api.schemas.web_workspaces_ds import OverviewCard, WorkspaceOverviewResponse
from app.modules.electronic_forms.governance_ds import ManagedFormError, ManagedFormService
from app.modules.identity_access.web_policy_ds import (
    WebWorkspace,
    allows_workspace,
    resolve_plant_factory,
)
from app.modules.submission_ledger.service_ds import (
    SubmissionLedgerError,
    SubmissionLedgerService,
)
from app.modules.workflow_engine.service_ds import WorkflowService

router = APIRouter(prefix="/api/v1/plant", tags=["plant"])


def _plant_actor(request: Request):  # type: ignore[no-untyped-def]
    actor = require_web_actor(request)
    if not allows_workspace(actor, WebWorkspace.PLANT_MANAGER):
        raise HTTPException(
            status_code=403,
            detail={"code": "WEB_ROLE_FORBIDDEN", "detail": "当前账号不能进入厂长工作区。"},
        )
    try:
        plant_id = resolve_plant_factory(actor, None)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "FACTORY_REQUIRED", "detail": str(error)},
        ) from error
    return actor, plant_id


def _forms(request: Request) -> ManagedFormService:
    return ManagedFormService(request.app.state.services.engine)


def _workflows(request: Request) -> WorkflowService:
    return WorkflowService(request.app.state.services.engine)


def _ledger(request: Request) -> SubmissionLedgerService:
    return SubmissionLedgerService(request.app.state.services.engine)


@router.get("/overview", response_model=WorkspaceOverviewResponse)
def overview(
    request: Request,
    factory_id: str | None = Query(default=None),
) -> WorkspaceOverviewResponse:
    actor = require_web_actor(request)
    if not allows_workspace(actor, WebWorkspace.PLANT_MANAGER):
        raise HTTPException(
            status_code=403,
            detail={"code": "WEB_ROLE_FORBIDDEN", "detail": "当前账号不能进入厂长工作区。"},
        )
    try:
        selected_factory = resolve_plant_factory(actor, factory_id)
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

    factory_name = (
        actor.factory_name if selected_factory == actor.factory_id else ""
    )
    return WorkspaceOverviewResponse(
        workspace=WebWorkspace.PLANT_MANAGER.value,
        title="本厂概览",
        scope="FACTORY",
        factory_id=selected_factory,
        factory_name=factory_name,
        cards=[
            OverviewCard(key="today_production", label="今日生产", value=0),
            OverviewCard(key="employees", label="本厂员工", value=0),
            OverviewCard(key="exceptions", label="待处理异常", value=0),
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
    _, plant_id = _plant_actor(request)
    return {"items": _workflows(request).list_plant(plant_id)}


@router.get("/production")
def production(request: Request) -> dict[str, object]:
    _, plant_id = _plant_actor(request)
    service = _ledger(request)
    return {
        "overview": service.overview(plant_id),
        "records": service.list_ledger(plant_id)["items"],
    }


@router.get("/exceptions")
def exceptions(request: Request) -> dict[str, object]:
    _, plant_id = _plant_actor(request)
    service = _ledger(request)
    return {
        "corrections": service.list_corrections(plant_id)["items"],
        "tasks": service.list_tasks(plant_id)["items"],
    }


@router.post("/submissions/{submission_id}/return")
def return_submission(
    submission_id: str,
    body: ReturnSubmissionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, str]:
    actor, plant_id = _plant_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _ledger(request).return_submission(
            submission_id,
            factory_id=plant_id,
            reason=body.reason,
            requested_by=actor.employee_code,
            assigned_to=body.assigned_to,
        )
    except SubmissionLedgerError as error:
        status_code = 403 if error.code == "CROSS_FACTORY_FORBIDDEN" else 409
        raise HTTPException(
            status_code=status_code,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.get("/notifications", response_model=ManagementNotificationListResponse)
def notifications(request: Request) -> ManagementNotificationListResponse:
    _, plant_id = _plant_actor(request)
    return ManagementNotificationListResponse(
        items=[
            ManagementNotificationResponse.model_validate(item)
            for item in _forms(request).list_notifications(plant_id)
        ]
    )


@router.post(
    "/notifications/{notification_id}/acknowledge",
    response_model=ManagementNotificationResponse,
)
def acknowledge_notification(
    notification_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> ManagementNotificationResponse:
    actor, plant_id = _plant_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        payload = _forms(request).acknowledge_notification(
            notification_id,
            plant_id=plant_id,
            actor_id=actor.employee_code,
        )
    except ManagedFormError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": error.code, "detail": error.detail},
        ) from error
    return ManagementNotificationResponse.model_validate(payload)
