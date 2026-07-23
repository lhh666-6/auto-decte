"""Phase 1 administrator workspace endpoints."""

from fastapi import APIRouter, HTTPException, Request

from app.api.routers.web_auth_ds import require_web_actor
from app.api.schemas.web_workspaces_ds import OverviewCard, WorkspaceOverviewResponse
from app.modules.identity_access.web_policy_ds import WebWorkspace, allows_workspace

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/overview", response_model=WorkspaceOverviewResponse)
def overview(request: Request) -> WorkspaceOverviewResponse:
    actor = require_web_actor(request)
    if not allows_workspace(actor, WebWorkspace.ADMIN):
        raise HTTPException(
            status_code=403,
            detail={"code": "WEB_ROLE_FORBIDDEN", "detail": "当前账号不能进入管理员工作区。"},
        )
    return WorkspaceOverviewResponse(
        workspace=WebWorkspace.ADMIN.value,
        title="系统概览",
        scope="GLOBAL",
        cards=[
            OverviewCard(key="pending_approvals", label="待审核", value=0),
            OverviewCard(key="version_exceptions", label="版本异常", value=0),
            OverviewCard(key="high_risk_events", label="高风险操作", value=0),
        ],
    )
