"""Phase 1 administrator workspace endpoints."""

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.routers.web_auth_ds import require_web_actor, require_web_csrf
from app.api.schemas.managed_forms_ds import (
    ApprovalDecisionRequest,
    ManagedFormListResponse,
    ManagedFormVersionResponse,
    PlantActivationRequest,
    PlantActivationResponse,
)
from app.api.schemas.web_workspaces_ds import OverviewCard, WorkspaceOverviewResponse
from app.modules.electronic_forms.governance_ds import ManagedFormError, ManagedFormService
from app.modules.identity_access.web_policy_ds import WebWorkspace, allows_workspace

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


def _admin_actor(request: Request):  # type: ignore[no-untyped-def]
    actor = require_web_actor(request)
    if not allows_workspace(actor, WebWorkspace.ADMIN):
        raise HTTPException(
            status_code=403,
            detail={"code": "WEB_ROLE_FORBIDDEN", "detail": "当前账号不能进入管理员工作区。"},
        )
    return actor


def _forms(request: Request) -> ManagedFormService:
    return ManagedFormService(request.app.state.services.engine)


def _form_error(error: ManagedFormError) -> HTTPException:
    status_code = 404 if error.code.endswith("NOT_FOUND") else 409
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "detail": error.detail},
    )


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


@router.get("/form-approvals", response_model=ManagedFormListResponse)
def form_approvals(request: Request) -> ManagedFormListResponse:
    _admin_actor(request)
    return ManagedFormListResponse(
        items=[
            ManagedFormVersionResponse.model_validate(item)
            for item in _forms(request).list_approvals()
        ]
    )


@router.post(
    "/form-approvals/{version_id}/decision",
    response_model=ManagedFormVersionResponse,
)
def decide_form_approval(
    version_id: str,
    body: ApprovalDecisionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> ManagedFormVersionResponse:
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        payload = _forms(request).decide(
            version_id,
            decision=body.decision,
            comment=body.comment,
            actor_id=actor.employee_code,
        )
    except ManagedFormError as error:
        raise _form_error(error) from error
    return ManagedFormVersionResponse.model_validate(payload)


def _activation_action(
    version_id: str,
    body: PlantActivationRequest,
    request: Request,
    csrf_token: str | None,
    action: str,
) -> PlantActivationResponse:
    actor = _admin_actor(request)
    require_web_csrf(request, csrf_token)
    try:
        payload = _forms(request).set_activation(
            version_id,
            plant_ids=body.plant_ids,
            action=action,
            actor_id=actor.employee_code,
        )
    except ManagedFormError as error:
        raise _form_error(error) from error
    return PlantActivationResponse.model_validate(payload)


@router.post(
    "/form-versions/{version_id}/activate",
    response_model=PlantActivationResponse,
)
def activate_form_version(
    version_id: str,
    body: PlantActivationRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> PlantActivationResponse:
    return _activation_action(version_id, body, request, x_csrf_token, "activate")


@router.post(
    "/form-versions/{version_id}/disable",
    response_model=PlantActivationResponse,
)
def disable_form_version(
    version_id: str,
    body: PlantActivationRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> PlantActivationResponse:
    return _activation_action(version_id, body, request, x_csrf_token, "disable")


@router.post(
    "/form-versions/{version_id}/restore",
    response_model=PlantActivationResponse,
)
def restore_form_version(
    version_id: str,
    body: PlantActivationRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> PlantActivationResponse:
    return _activation_action(version_id, body, request, x_csrf_token, "restore")


@router.post(
    "/form-versions/{version_id}/retire",
    response_model=PlantActivationResponse,
)
def retire_form_version(
    version_id: str,
    body: PlantActivationRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> PlantActivationResponse:
    return _activation_action(version_id, body, request, x_csrf_token, "retire")
