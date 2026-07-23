"""Phase 1 finance workspace endpoints."""

from urllib.parse import quote

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from fastapi.responses import Response

from app.api.routers.web_auth_ds import require_web_actor, require_web_csrf
from app.api.schemas.business_workflows_ds import (
    ConfirmDiscoveryRequest,
    CreateDiscoverySessionRequest,
    CreateWorkflowRequest,
    DiscoveryMessageRequest,
)
from app.api.schemas.managed_forms_ds import (
    CreateManagedFormRequest,
    ManagedFormListResponse,
    ManagedFormVersionResponse,
    UpdateManagedFormVersionRequest,
)
from app.api.schemas.payroll_rules_ds import (
    CalculatePayrollRequest,
    CreatePayrollRuleRequest,
)
from app.api.schemas.report_templates_ds import (
    CreateGovernedExportRequest,
    CreateReportMappingRequest,
)
from app.api.schemas.submission_ledger_ds import (
    AttachReplacementRequest,
    ReviewCorrectionRequest,
)
from app.api.schemas.web_workspaces_ds import OverviewCard, WorkspaceOverviewResponse
from app.modules.business_discovery.service_ds import (
    BusinessDiscoveryError,
    BusinessDiscoveryService,
)
from app.modules.electronic_forms.governance_ds import ManagedFormError, ManagedFormService
from app.modules.identity_access.web_policy_ds import WebWorkspace, allows_workspace
from app.modules.payroll_rules.service_ds import PayrollError, PayrollService
from app.modules.report_templates.service_ds import (
    ReportTemplateError,
    ReportTemplateService,
)
from app.modules.submission_ledger.service_ds import (
    SubmissionLedgerError,
    SubmissionLedgerService,
)
from app.modules.workflow_engine.service_ds import WorkflowError, WorkflowService

router = APIRouter(prefix="/api/v1/finance", tags=["finance"])


def _finance_actor(request: Request):  # type: ignore[no-untyped-def]
    actor = require_web_actor(request)
    if not allows_workspace(actor, WebWorkspace.FINANCE):
        raise HTTPException(
            status_code=403,
            detail={"code": "WEB_ROLE_FORBIDDEN", "detail": "当前账号不能进入财务工作区。"},
        )
    return actor


def _forms(request: Request) -> ManagedFormService:
    return ManagedFormService(request.app.state.services.engine)


def _discovery(request: Request) -> BusinessDiscoveryService:
    return BusinessDiscoveryService(request.app.state.services.engine)


def _workflows(request: Request) -> WorkflowService:
    return WorkflowService(request.app.state.services.engine)


def _ledger(request: Request) -> SubmissionLedgerService:
    return SubmissionLedgerService(request.app.state.services.engine)


def _payroll(request: Request) -> PayrollService:
    return PayrollService(request.app.state.services.engine)


def _reports(request: Request) -> ReportTemplateService:
    return ReportTemplateService(request.app.state.services.engine)


def _form_error(error: ManagedFormError) -> HTTPException:
    conflict_codes = {
        "FORM_KEY_EXISTS",
        "FORM_VERSION_IMMUTABLE",
        "FORM_VERSION_REVISION_CONFLICT",
        "FORM_VERSION_NOT_DRAFT",
    }
    return HTTPException(
        status_code=409 if error.code in conflict_codes else 404,
        detail={"code": error.code, "detail": error.detail},
    )


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


@router.get("/ledger/overview")
def ledger_overview(request: Request, factory_id: str = Query(default="")) -> dict[str, int]:
    _finance_actor(request)
    return _ledger(request).overview(factory_id or None)


@router.get("/ledger")
def ledger(request: Request, factory_id: str = Query(default="")) -> dict[str, object]:
    _finance_actor(request)
    return _ledger(request).list_ledger(factory_id or None)


@router.get("/corrections")
def corrections(request: Request, factory_id: str = Query(default="")) -> dict[str, object]:
    _finance_actor(request)
    return _ledger(request).list_corrections(factory_id or None)


@router.get("/business-tasks")
def business_tasks(request: Request, factory_id: str = Query(default="")) -> dict[str, object]:
    _finance_actor(request)
    return _ledger(request).list_tasks(factory_id or None)


@router.get("/payroll-rules")
def payroll_rules(request: Request) -> dict[str, object]:
    _finance_actor(request)
    return _payroll(request).list_rules()


@router.post("/payroll-rules", status_code=status.HTTP_201_CREATED)
def create_payroll_rule(
    body: CreatePayrollRuleRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _payroll(request).create_rule(
            **body.model_dump(), actor_id=actor.employee_code
        )
    except PayrollError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/payroll-rules/{version_id}/submit-approval")
def submit_payroll_rule(
    version_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _payroll(request).submit_rule(version_id)
    except PayrollError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/payroll-calculations", status_code=status.HTTP_201_CREATED)
def calculate_payroll(
    body: CalculatePayrollRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _payroll(request).calculate(
            **body.model_dump(), actor_id=actor.employee_code
        )
    except PayrollError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.get("/payroll-calculations")
def payroll_batches(request: Request) -> dict[str, object]:
    _finance_actor(request)
    return _payroll(request).list_batches()


@router.post("/payroll-calculations/{batch_id}/confirm")
def confirm_payroll_batch(
    batch_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _payroll(request).confirm_batch(batch_id, actor_id=actor.employee_code)
    except PayrollError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.get("/payroll")
def finance_payroll(
    request: Request,
    factory_id: str = Query(default=""),
    employee_code: str = Query(default=""),
) -> dict[str, object]:
    actor = _finance_actor(request)
    return _payroll(request).list_official(
        factory_id=factory_id or None,
        employee_code=employee_code or None,
        actor_id=actor.employee_code,
        actor_role="FINANCE",
    )


@router.get("/report-templates")
def report_templates(request: Request) -> dict[str, object]:
    _finance_actor(request)
    return _reports(request).list_templates()


@router.post("/report-templates/{template_version_id}/analyze")
def analyze_report_template(
    template_version_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _reports(request).get_template(template_version_id)
    except ReportTemplateError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.get("/report-mappings")
def report_mappings(
    request: Request,
    template_version_id: str = Query(default=""),
) -> dict[str, object]:
    _finance_actor(request)
    return _reports(request).list_mappings(template_version_id or None)


@router.post("/report-mappings", status_code=201)
def create_report_mapping(
    body: CreateReportMappingRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _reports(request).create_mapping(
            **body.model_dump(), actor_id=actor.employee_code
        )
    except ReportTemplateError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/report-mappings/{mapping_version_id}/confirm")
def confirm_report_mapping(
    mapping_version_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _reports(request).confirm_mapping(
            mapping_version_id, actor_id=actor.employee_code
        )
    except ReportTemplateError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/exports", status_code=201)
def create_governed_export(
    body: CreateGovernedExportRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    ledger_service = _ledger(request)
    factory_id = str(body.filters.get("factory_id", "")).strip() or None
    source_records = ledger_service.list_ledger(factory_id)["items"]
    records: list[dict[str, object]] = []
    if not isinstance(source_records, list):
        source_records = []
    for item in source_records:
        if not isinstance(item, dict):
            continue
        record = dict(item)
        values = record.pop("values", {})
        if isinstance(values, dict):
            record.update(values)
        record["submission_id"] = record["effective_submission_id"]
        records.append(record)
    try:
        return _reports(request).create_export(
            template_version_id=body.template_version_id,
            mapping_version_id=body.mapping_version_id,
            idempotency_key=body.idempotency_key,
            filters=body.filters,
            records=records,
            data_watermark=ledger_service.watermark(),
            actor_id=actor.employee_code,
        )
    except ReportTemplateError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.get("/exports")
def governed_exports(request: Request) -> dict[str, object]:
    _finance_actor(request)
    return _reports(request).list_exports()


@router.get("/exports/{export_batch_id}")
def governed_export(export_batch_id: str, request: Request) -> dict[str, object]:
    _finance_actor(request)
    try:
        return _reports(request).get_export(export_batch_id)
    except ReportTemplateError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.get("/exports/{export_batch_id}/download")
def download_governed_export(export_batch_id: str, request: Request) -> Response:
    _finance_actor(request)
    try:
        batch = _reports(request).get_export(export_batch_id)
        content = _reports(request).download(export_batch_id)
    except ReportTemplateError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{quote(str(batch['download_name']))}"
            )
        },
    )


@router.get("/exports/{export_batch_id}/lineage")
def governed_export_lineage(
    export_batch_id: str, request: Request
) -> dict[str, object]:
    _finance_actor(request)
    return _reports(request).lineage(export_batch_id)


@router.post("/corrections/{correction_id}/replacement")
def attach_correction_replacement(
    correction_id: str,
    body: AttachReplacementRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, str]:
    _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _ledger(request).attach_replacement(correction_id, **body.model_dump())
    except SubmissionLedgerError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/corrections/{correction_id}/review")
def review_correction(
    correction_id: str,
    body: ReviewCorrectionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, str]:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _ledger(request).review_correction(
            correction_id,
            approved=body.approved,
            reviewer_id=actor.employee_code,
            note=body.note,
        )
    except SubmissionLedgerError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.get("/form-definitions", response_model=ManagedFormListResponse)
def form_definitions(request: Request) -> ManagedFormListResponse:
    _finance_actor(request)
    return ManagedFormListResponse(
        items=[
            ManagedFormVersionResponse.model_validate(item)
            for item in _forms(request).list_definitions()
        ]
    )


@router.post(
    "/form-definitions",
    response_model=ManagedFormVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_form_definition(
    body: CreateManagedFormRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> ManagedFormVersionResponse:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        payload = _forms(request).create_definition(
            **body.model_dump(by_alias=True),
            actor_id=actor.employee_code,
        )
    except ManagedFormError as error:
        raise _form_error(error) from error
    return ManagedFormVersionResponse.model_validate(payload)


@router.get(
    "/form-versions/{version_id}",
    response_model=ManagedFormVersionResponse,
)
def form_version(version_id: str, request: Request) -> ManagedFormVersionResponse:
    _finance_actor(request)
    try:
        payload = _forms(request).get_version(version_id)
    except ManagedFormError as error:
        raise _form_error(error) from error
    return ManagedFormVersionResponse.model_validate(payload)


@router.patch(
    "/form-versions/{version_id}",
    response_model=ManagedFormVersionResponse,
)
def update_form_version(
    version_id: str,
    body: UpdateManagedFormVersionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> ManagedFormVersionResponse:
    _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        payload = _forms(request).update_draft(
            version_id,
            **body.model_dump(by_alias=True),
        )
    except ManagedFormError as error:
        raise _form_error(error) from error
    return ManagedFormVersionResponse.model_validate(payload)


@router.post(
    "/form-versions/{version_id}/submit-approval",
    response_model=ManagedFormVersionResponse,
)
def submit_form_approval(
    version_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> ManagedFormVersionResponse:
    _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        payload = _forms(request).submit_approval(version_id)
    except ManagedFormError as error:
        raise _form_error(error) from error
    return ManagedFormVersionResponse.model_validate(payload)


@router.post(
    "/form-versions/{version_id}/clone",
    response_model=ManagedFormVersionResponse,
    status_code=status.HTTP_201_CREATED,
)
def clone_form_version(
    version_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> ManagedFormVersionResponse:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        payload = _forms(request).clone(version_id, actor.employee_code)
    except ManagedFormError as error:
        raise _form_error(error) from error
    return ManagedFormVersionResponse.model_validate(payload)


@router.post("/business-discovery/sessions", status_code=status.HTTP_201_CREATED)
def create_discovery_session(
    body: CreateDiscoverySessionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    return _discovery(request).create_session(
        **body.model_dump(),
        actor_id=actor.employee_code,
    )


@router.post("/business-discovery/sessions/{session_id}/messages")
def add_discovery_message(
    session_id: str,
    body: DiscoveryMessageRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _discovery(request).add_message(session_id, content=body.content)
    except BusinessDiscoveryError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/business-discovery/sessions/{session_id}/confirm")
def confirm_discovery(
    session_id: str,
    body: ConfirmDiscoveryRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _discovery(request).confirm(
            session_id,
            **body.model_dump(),
            actor_id=actor.employee_code,
        )
    except BusinessDiscoveryError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
def create_workflow(
    body: CreateWorkflowRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    actor = _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _workflows(request).create(
            **body.model_dump(),
            actor_id=actor.employee_code,
        )
    except WorkflowError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/workflow-versions/{version_id}/validate")
def validate_workflow(
    version_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _workflows(request).validate(version_id)
    except WorkflowError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.post("/workflow-versions/{version_id}/submit-approval")
def submit_workflow(
    version_id: str,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict[str, object]:
    _finance_actor(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _workflows(request).submit(version_id)
    except WorkflowError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": error.code, "detail": error.detail},
        ) from error
