"""Phase 1 administrator workspace endpoints."""

from typing import Any, cast
from urllib.parse import unquote

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.routers.web_auth_ds import require_web_actor, require_web_csrf
from app.api.schemas.bamboo_process_ds import (
    AdminCreateEmployeeRequest,
    AdminCreateFactoryRequest,
)
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
from app.application.personnel_governance_ds import (
    PersonnelGovernanceError,
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


class SetAccountStateRequest(BaseModel):
    state: str = Field(..., pattern="^(ACTIVE|FROZEN|REMOVED)$")


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
    # SYSTEM_ADMIN intentionally excluded from admin creation UI (§11-12)
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


@router.get("/factories-all")
def list_all_factories(request: Request) -> dict[str, object]:
    """List ALL factories including inactive (for factory management page)."""
    _admin_actor(request)
    try:
        factories = _bamboo(request).list_all_factories()
    except BambooOperationError as error:
        raise _bamboo_error(error) from error
    return {"items": factories}


@router.post("/factories", status_code=status.HTTP_201_CREATED)
def admin_create_factory(
    body: AdminCreateFactoryRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    """Admin creates a new factory. factory_code is auto-generated if not provided."""
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _bamboo(request).create_factory(
            actor=_admin_bamboo_actor(actor, ""),
            name=body.name,
            code=body.code,
            activate_forms=body.activate_forms,
        )
    except BambooOperationError as error:
        raise _bamboo_error(error) from error


@router.put("/factories/{factory_id}/deactivate")
def admin_deactivate_factory(
    factory_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    """Admin deactivates a factory."""
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _bamboo(request).deactivate_factory(
            actor=_admin_bamboo_actor(actor, factory_id),
            factory_id=factory_id,
        )
    except BambooOperationError as error:
        raise _bamboo_error(error) from error


@router.put("/factories/{factory_id}/activate")
def admin_activate_factory(
    factory_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    """Admin re-activates a deactivated factory."""
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _bamboo(request).activate_factory(
            actor=_admin_bamboo_actor(actor, factory_id),
            factory_id=factory_id,
        )
    except BambooOperationError as error:
        raise _bamboo_error(error) from error


@router.get("/employees/next-code")
def preview_employee_code(
    factory_id: str,
    position: str,
    request: Request,
) -> dict[str, object]:
    """Preview the next employee code for a factory+position pair (does not consume)."""
    _admin_actor(request)
    try:
        code = _bamboo(request).preview_employee_code(factory_id, position)
    except BambooOperationError as error:
        raise _bamboo_error(error) from error
    return {"employee_code": code}


@router.get("/job-presets")
def list_job_presets(request: Request) -> dict[str, object]:
    """Return the canonical job presets with Chinese labels and role mappings."""
    _admin_actor(request)
    return {"items": _ADMIN_JOB_PRESETS}


@router.get("/employees")
def admin_list_employees(
    request: Request,
    factory_id: str | None = None,
) -> dict[str, object]:
    """Admin lists all employees (ACTIVE/FROZEN/REMOVED) with account state.

    V1 Runtime Closure §6.5: factory_id filter must actually work.
    Shows current/last position and account state for all employees.
    """
    _admin_actor(request)
    services: Any = request.app.state.services
    engine = services.engine

    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.adapters.database.models import (
        EmployeeBambooAssignmentRow,
        MasterDataRecordRow,
        MobileAccessProfileRow,
    )

    with Session(engine) as session:
        # Query all employees from master data (not just ACTIVE assignments)
        emp_query = select(MasterDataRecordRow).where(
            MasterDataRecordRow.catalog == "employees",
        )
        employees = session.scalars(emp_query).all()

        result: list[dict[str, Any]] = []
        for emp in employees:
            # Get account state from profile
            profile = session.scalar(
                select(MobileAccessProfileRow).where(
                    MobileAccessProfileRow.employee_code == emp.code
                )
            )
            account_state = profile.account_state if profile else "ACTIVE"
            is_active_profile = profile.active if profile else True

            # Get current/last assignment
            assignment_query = select(EmployeeBambooAssignmentRow).where(
                EmployeeBambooAssignmentRow.employee_code == emp.code,
            )
            if factory_id:
                assignment_query = assignment_query.where(
                    EmployeeBambooAssignmentRow.factory_id == factory_id
                )
            assignment = session.scalar(
                assignment_query.order_by(
                    EmployeeBambooAssignmentRow.effective_at.desc()
                ).limit(1)
            )

            # V1 §6.5: factory_id filter must exclude employees without
            # any assignment in that factory
            if factory_id and assignment is None:
                continue

            result.append({
                "employee_code": emp.code,
                "employee_name": emp.display_name,
                "factory_id": assignment.factory_id if assignment else "",
                "role_code": assignment.role_code if assignment else "",
                "assignment_status": assignment.status if assignment else "NONE",
                "account_state": account_state,
                "active": is_active_profile,
            })

        return {"items": sorted(
            result,
            key=lambda item: (item["account_state"], item["employee_name"]),
        )}


@router.get("/personnel-transfers")
def admin_personnel_transfers(request: Request) -> dict[str, object]:
    """Admin lists all personnel transfers."""
    _admin_actor(request)
    actor_info = require_web_actor(request)
    dummy_actor = _admin_bamboo_actor(actor_info, "ADMIN")
    return {"items": _bamboo(request).list_personnel_transfers(dummy_actor)}


@router.post("/employees", status_code=status.HTTP_201_CREATED)
def admin_create_employee(
    body: AdminCreateEmployeeRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, object]:
    """Admin creates a new employee. Employee code is auto-generated server-side."""
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _bamboo(request).create_factory_employee(
            actor=_admin_bamboo_actor(actor, body.factory_id),
            employee_name=body.employee_name,
            initial_pin=body.initial_pin,
            role_code=body.bamboo_role,
            factory_id=body.factory_id,
            web_roles=body.web_roles,
        )
    except BambooOperationError as error:
        raise _bamboo_error(error) from error


# ── Employee Account State (Freeze / Restore / Remove) ──────────


@router.put("/employees/{employee_code}/account-state")
async def set_employee_account_state(
    employee_code: str,
    body: SetAccountStateRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict:
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    services: Any = request.app.state.services
    try:
        return services.personnel.set_account_state(
            employee_code,
            body.state,
            actor_id=actor.employee_code,
        )
    except PersonnelGovernanceError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.get("/form-definitions")
def admin_form_definitions(request: Request) -> dict[str, object]:
    """Admin lists all managed form definitions with latest version."""
    _admin_actor(request)
    return {"items": _forms(request).list_definitions()}


@router.get("/employees/{employee_code}/account-state")
async def get_employee_account_state(
    employee_code: str,
    request: Request,
) -> dict | None:
    _admin_actor(request)
    services: Any = request.app.state.services
    result = services.personnel.get_account_state(employee_code)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
    return result


# ── Management Salary ──────────────────────────────────────────


class CreateManagementSalaryRequest(BaseModel):
    employee_code: str = Field(...)
    factory_id: str = Field(...)
    position_snapshot: str = Field(...)
    role_code_snapshot: str = Field(...)
    salary_type: str = Field(default="FIXED_MANAGEMENT")
    amount: str = Field(...)
    effective_from: str = Field(...)


@router.post("/management-salaries", status_code=201)
async def create_management_salary(
    body: CreateManagementSalaryRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict:
    actor = _admin_actor(request)
    require_web_csrf(request, x_csrf_token)
    services: Any = request.app.state.services
    return services.management_salary.create_salary(
        employee_code=body.employee_code,
        factory_id=body.factory_id,
        position_snapshot=body.position_snapshot,
        role_code_snapshot=body.role_code_snapshot,
        salary_type=body.salary_type,
        amount=body.amount,
        effective_from=body.effective_from,
        created_by=actor.employee_code,
    )


@router.get("/management-salaries")
async def list_management_salaries(
    request: Request,
    factory_id: str | None = None,
) -> list[dict]:
    _admin_actor(request)
    services: Any = request.app.state.services
    return services.management_salary.list_salaries(factory_id)


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
