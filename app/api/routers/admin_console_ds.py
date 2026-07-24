"""Phase 1 administrator workspace endpoints."""

from typing import Any, cast
from urllib.parse import unquote

from fastapi import APIRouter, Header, HTTPException, Query, Request, status

from app.api.routers.web_auth_ds import require_web_actor, require_web_csrf
from app.api.schemas.bamboo_process_ds import AdminCreateEmployeeRequest
from app.api.schemas.business_workflows_ds import (
    WorkflowActivationRequest,
    WorkflowApprovalDecisionRequest,
)
from app.api.schemas.managed_forms_ds import (
    ApprovalDecisionRequest,
    ManagedFormListResponse,
    ManagedFormVersionResponse,
    PlantActivationRequest,
    PlantActivationResponse,
)
from app.api.schemas.payroll_rules_ds import (
    CalculatePayrollRequest,
    PayrollDecisionRequest,
    RecalculatePayrollRequest,
)
from app.api.schemas.web_workspaces_ds import OverviewCard, WorkspaceOverviewResponse
from app.application.bamboo_operations_ds import (
    BambooOperationError,
    BambooOperationsService,
)
from app.modules.bamboo_process.models_ds import BambooRole
from app.modules.electronic_forms.governance_ds import ManagedFormError, ManagedFormService
from app.modules.identity_access.web_policy_ds import WebWorkspace, allows_workspace
from app.modules.payroll_rules.service_ds import PayrollError, PayrollService
from app.modules.report_templates.service_ds import (
    ReportTemplateError,
    ReportTemplateService,
)
from app.modules.workflow_engine.service_ds import WorkflowError, WorkflowService

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


def _workflows(request: Request) -> WorkflowService:
    return WorkflowService(request.app.state.services.engine)


def _payroll(request: Request) -> PayrollService:
    return PayrollService(request.app.state.services.engine)


def _reports(request: Request) -> ReportTemplateService:
    return ReportTemplateService(request.app.state.services.engine)


def _bamboo(request: Request) -> BambooOperationsService:
    return cast(BambooOperationsService, request.app.state.services.bamboo_operations)


# ── Admin Job Presets ──
# Maps the admin-facing Chinese position label to internal bamboo_role + web_roles.
_ADMIN_JOB_PRESETS: list[dict[str, object]] = [
    {"label": "分选工",     "bamboo_role": "SORT_OPERATOR",      "web_roles": []},
    {"label": "浸胶工",     "bamboo_role": "DIPPING_OPERATOR",    "web_roles": []},
    {"label": "干燥工",     "bamboo_role": "DRYING_RACK_OPERATOR", "web_roles": []},
    {"label": "检测人",     "bamboo_role": "INSPECTOR",           "web_roles": []},
    {"label": "主管",       "bamboo_role": "SUPERVISOR",           "web_roles": []},
    {"label": "厂长",       "bamboo_role": "PLANT_MANAGER",        "web_roles": ["PLANT_MANAGER"]},
    {"label": "财务审批",   "bamboo_role": "FINANCE_APPROVER",     "web_roles": ["FINANCE"]},
    {"label": "系统管理员", "bamboo_role": "SYSTEM_ADMIN",          "web_roles": ["ADMIN"]},
]


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
    form_approvals = _forms(request).list_approvals()
    workflow_approvals = _workflows(request).list_pending()
    payroll_items = _payroll(request).list_rules(approvals_only=True).get("items", [])
    form_count = len(form_approvals)
    workflow_count = len(workflow_approvals)
    payroll_count = len(payroll_items) if isinstance(payroll_items, list) else 0
    return WorkspaceOverviewResponse(
        workspace=WebWorkspace.ADMIN.value,
        title="系统概览",
        scope="GLOBAL",
        cards=[
            OverviewCard(
                key="pending_form_approvals",
                label="待表单审批",
                value=form_count,
            ),
            OverviewCard(
                key="pending_workflow_approvals",
                label="待流程审批",
                value=workflow_count,
            ),
            OverviewCard(
                key="pending_payroll_approvals",
                label="待工资规则审批",
                value=payroll_count,
            ),
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


@router.get("/payroll-approvals")
def payroll_approvals(request: Request) -> dict[str, object]:
    _admin_actor(request)
    return _payroll(request).list_rules(approvals_only=True)


@router.post("/payroll-approvals/{version_id}/decision")
def decide_payroll_rule(
    version_id: str,
    body: PayrollDecisionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _payroll(request).decide_rule(
            version_id,
            approved=body.approved,
            actor_id=actor.employee_code,
            note=body.note,
        )
    except PayrollError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/payroll-approvals/{version_id}/trial")
def trial_payroll_rule(
    version_id: str,
    body: CalculatePayrollRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _payroll(request).calculate(
            **body.model_dump(),
            actor_id=actor.employee_code,
            dry_run=True,
        )
    except PayrollError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/payroll-recalculations", status_code=201)
def recalculate_payroll(
    body: RecalculatePayrollRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _payroll(request).recalculate(
            **body.model_dump(), actor_id=actor.employee_code
        )
    except PayrollError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.get("/payroll")
def admin_payroll(
    request: Request,
    factory_id: str = Query(default=""),
    employee_code: str = Query(default=""),
) -> dict[str, object]:
    actor = _admin_actor(request)
    return _payroll(request).list_official(
        factory_id=factory_id or None,
        employee_code=employee_code or None,
        actor_id=actor.employee_code,
        actor_role="ADMIN",
    )


@router.post("/report-templates", status_code=201)
async def upload_report_template(
    request: Request,
    x_filename: str = Header(alias="X-Filename"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    content = await request.body()
    try:
        return _reports(request).upload_template(
            filename=unquote(x_filename),
            mime_type=request.headers.get("content-type", "application/octet-stream"),
            content=content,
            actor_id=actor.employee_code,
        )
    except ReportTemplateError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "detail": error.detail},
        ) from error


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


@router.get("/workflow-approvals")
def workflow_approvals(request: Request) -> dict[str, object]:
    _admin_actor(request)
    return {"items": _workflows(request).list_pending()}


@router.post("/workflow-approvals/{version_id}/decision")
def decide_workflow_approval(
    version_id: str,
    body: WorkflowApprovalDecisionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _workflows(request).decide(
            version_id,
            decision=body.decision,
            actor_id=actor.employee_code,
        )
    except WorkflowError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/workflow-versions/{version_id}/activate")
def activate_workflow(
    version_id: str,
    body: WorkflowActivationRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _workflows(request).activate(
            version_id,
            plant_ids=body.plant_ids,
            actor_id=actor.employee_code,
        )
    except WorkflowError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


# ─────────────────────────────────────────────────────────────
# Admin Organization & Employee Management
# ─────────────────────────────────────────────────────────────


def _bamboo_error(error: BambooOperationError) -> HTTPException:
    status_code = 404 if error.code.endswith("NOT_FOUND") else 409
    return HTTPException(
        status_code=status_code,
        detail={"code": error.code, "detail": str(error)},
    )


@router.get("/factories")
def list_admin_factories(request: Request) -> dict[str, object]:
    """List all active factories (for admin employee creation dropdown)."""
    _admin_actor(request)
    try:
        factories = _bamboo(request).list_factories_for_admin()
    except BambooOperationError as error:
        raise _bamboo_error(error) from error
    return {"items": factories}


@router.get("/job-presets")
def list_job_presets(request: Request) -> dict[str, object]:
    """Return the canonical job presets with Chinese labels and role mappings."""
    _admin_actor(request)
    return {"items": _ADMIN_JOB_PRESETS}


@router.post("/employees", status_code=status.HTTP_201_CREATED)
def admin_create_employee(
    body: AdminCreateEmployeeRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    """Admin creates a new employee with factory + job preset selection."""
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _bamboo(request).create_factory_employee(
            actor=_admin_bamboo_actor(actor, body.factory_id),
            employee_name=body.employee_name,
            initial_pin=body.initial_pin,
            role_code=body.bamboo_role,
            employee_code=body.employee_code,
            factory_id=body.factory_id,
            web_roles=body.web_roles,
        )
    except BambooOperationError as error:
        raise _bamboo_error(error) from error


def _admin_bamboo_actor(web_actor: Any, factory_id: str) -> Any:
    """Build a BambooActor from a web actor for admin operations."""
    from app.modules.bamboo_process.models_ds import BambooActor
    return BambooActor(
        actor_id=web_actor.employee_code,
        employee_code=web_actor.employee_code,
        employee_name=web_actor.employee_name,
        factory_id=factory_id,
        factory_name="",
        role=BambooRole.SYSTEM_ADMIN,
    )
