"""Phase 1 factory-scoped plant manager workspace endpoints."""

from fastapi import APIRouter, Header, HTTPException, Query, Request

from app.api.routers.web_auth_ds import require_web_actor, require_web_csrf
from app.api.schemas.managed_forms_ds import (
    ManagedFormListResponse,
    ManagedFormVersionResponse,
    ManagementNotificationListResponse,
    ManagementNotificationResponse,
)
from app.api.schemas.web_workspaces_ds import OverviewCard, WorkspaceOverviewResponse
from app.modules.electronic_forms.governance_ds import ManagedFormError, ManagedFormService
from app.modules.identity_access.web_policy_ds import (
    WebWorkspace,
    allows_workspace,
    resolve_plant_factory,
)

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
