"""Phase 1 factory-scoped plant manager workspace endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.routers.web_auth_ds import require_web_actor
from app.api.schemas.web_workspaces_ds import OverviewCard, WorkspaceOverviewResponse
from app.modules.identity_access.web_policy_ds import (
    WebWorkspace,
    allows_workspace,
    resolve_plant_factory,
)

router = APIRouter(prefix="/api/v1/plant", tags=["plant"])


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
