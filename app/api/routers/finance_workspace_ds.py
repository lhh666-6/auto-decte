"""Phase 1 finance workspace endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.routers.web_auth_ds import require_web_actor
from app.api.schemas.web_workspaces_ds import OverviewCard, WorkspaceOverviewResponse
from app.modules.identity_access.web_policy_ds import WebWorkspace, allows_workspace

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


@router.get("/overview", response_model=WorkspaceOverviewResponse)
def overview(
    request: Request,
    factory_id: str = Query(default=""),
) -> WorkspaceOverviewResponse:
    actor = require_web_actor(request)
    if not allows_workspace(actor, WebWorkspace.FINANCE):
        raise HTTPException(
            status_code=403,
            detail={"code": "WEB_ROLE_FORBIDDEN", "detail": "当前账号不能进入财务工作区。"},
        )
    return WorkspaceOverviewResponse(
        workspace=WebWorkspace.FINANCE.value,
        title="财务概览",
        scope="GLOBAL",
        factory_id=factory_id,
        cards=[
            OverviewCard(key="today_submissions", label="今日新增提交", value=0),
            OverviewCard(key="pending_review", label="待审核记录", value=0),
            OverviewCard(key="exceptions", label="异常记录", value=0),
        ],
    )
