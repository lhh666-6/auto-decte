"""Phase 1 finance workspace endpoints."""

from fastapi import APIRouter, Header, HTTPException, Query, Request, status

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
