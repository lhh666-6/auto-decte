"""Server-authoritative electronic submission routes."""

from typing import cast

from fastapi import APIRouter, Header, HTTPException, Request

from app.api.routers.mobile_auth_ds import require_csrf, require_mobile_actor
from app.api.schemas.mobile_ds import CreateSubmissionRequest, SubmissionResponse
from app.application.electronic_submissions_ds import ElectronicFormCommand
from app.modules.electronic_forms.governance_ds import ManagedFormService
from app.modules.electronic_forms.models_ds import (
    DefinitionNotPublished,
    IdempotencyConflict,
)
from app.modules.master_data.models_ds import MasterDataCatalog
from app.services.container import Services

router = APIRouter()


def _services(request: Request) -> Services:
    return cast(Services, request.app.state.services)


@router.post("/submissions", response_model=SubmissionResponse)
def create_submission(
    body: CreateSubmissionRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> SubmissionResponse:
    actor = require_mobile_actor(request)
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": "IDEMPOTENCY_KEY_REQUIRED", "detail": "缺少幂等键。"},
        )
    require_csrf(request, x_csrf_token)
    if body.form_type not in actor.allowed_form_types:
        managed = ManagedFormService(_services(request).engine).resolve_active_form(
            actor.factory_id,
            body.form_type,
            actor.roles,
        )
        if managed is None:
            raise HTTPException(
                status_code=403,
                detail={"code": "FORM_TYPE_FORBIDDEN", "detail": "无权提交该表单。"},
            )
    else:
        managed = None
    if body.mode == "TEAM_LEADER_BATCH" and "TEAM_LEADER" not in actor.roles:
        raise HTTPException(
            status_code=403,
            detail={"code": "MODE_FORBIDDEN", "detail": "仅班组长可代填。"},
        )
    if body.mode == "SELF" and body.subject_employee_code != actor.employee_code:
        raise HTTPException(
            status_code=403,
            detail={"code": "SUBJECT_FORBIDDEN", "detail": "本人填报不能修改填报对象。"},
        )
    services = _services(request)
    if managed is not None:
        definition_version_id = str(managed["version_id"])
        template_id = str(managed["form_key"])
        template_version = str(managed["version"])
        job_profile_version = None
        managed_fields = cast(
            list[dict[str, object]],
            cast(dict[str, object], managed["schema_json"]).get("fields", []),
        )
        strategies = {
            str(field["key"]): "MANUAL_REQUIRED"
            if bool(field.get("required"))
            else "DEFAULT_EDITABLE"
            for field in managed_fields
        }
    else:
        try:
            definition = services.electronic_definitions.get_published(body.form_type)
        except DefinitionNotPublished as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "SCHEMA_VERSION_CONFLICT", "detail": "表单版本已失效。"},
            ) from error
        definition_version_id = definition.definition_version_id
        if definition.template_version_id is None:
            raise HTTPException(
                status_code=409,
                detail={"code": "DEFINITION_BINDING_INVALID", "detail": "表单未绑定模板。"},
            )
        template_id = definition.template_version_id
        template_version = str(definition.version)
        job_profile_version = definition.job_profile_version_id
        config = definition.presentation_config
        strategies = {
            field.field_key: field.strategy for field in (config.fields if config else [])
        }
    if definition_version_id != body.definition_version_id:
        raise HTTPException(
            status_code=409,
            detail={"code": "SCHEMA_VERSION_CONFLICT", "detail": "请刷新表单版本。"},
        )
    unknown = sorted(set(body.values) - set(strategies))
    computed = sorted(
        key for key in body.values if strategies.get(key) == "COMPUTED_READ_ONLY"
    )
    missing = (
        sorted(
            str(field["key"])
            for field in managed_fields
            if bool(field.get("required")) and str(field["key"]) not in body.values
        )
        if managed is not None
        else []
    )
    invalid_types = (
        sorted(
            str(field["key"])
            for field in managed_fields
            if str(field["key"]) in body.values
            and not _matches_managed_type(
                body.values[str(field["key"])],
                str(field.get("type", "text")),
            )
        )
        if managed is not None
        else []
    )
    if unknown or computed or missing or invalid_types:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SUBMISSION_FIELDS_INVALID",
                "detail": "提交字段不符合已发布定义。",
                "failures": {
                    "unknown": unknown,
                    "computed": computed,
                    "missing": missing,
                    "invalid_types": invalid_types,
                },
            },
        )
    employee = services.master_data_repository.get(
        MasterDataCatalog.EMPLOYEES,
        body.subject_employee_code,
    )
    if employee is None or not employee.active:
        raise HTTPException(
            status_code=422,
            detail={"code": "SUBJECT_INVALID", "detail": "填报对象不存在或已停用。"},
        )
    if body.mode == "TEAM_LEADER_BATCH":
        subject_profile = services.mobile_identity_repository.get_access_profile(
            body.subject_employee_code
        )
        if subject_profile is None or subject_profile.team_id != actor.team_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "SUBJECT_NOT_IN_TEAM",
                    "detail": "只能为当前班组的有效成员填报。",
                },
            )
    command = ElectronicFormCommand(
        form_type=body.form_type,
        definition_version_id=body.definition_version_id,
        mode=body.mode,
        actor_id=actor.employee_code,
        subject_employee_code=employee.code,
        subject_employee_name=employee.display_name,
        team_id=actor.team_id,
        team_name=actor.team_name,
        device_id=body.device_id,
        values=body.values,
        client_submission_id=idempotency_key.strip(),
        template_id=template_id,
        template_version=template_version,
        job_profile_version=job_profile_version,
        factory_id=actor.factory_id,
    )
    try:
        receipt = services.electronic_integration.accept(command)
    except IdempotencyConflict as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "IDEMPOTENCY_CONFLICT", "detail": "幂等键对应不同内容。"},
        ) from error
    return SubmissionResponse(
        submission_id=receipt.receipt_id,
        status=receipt.status.value,
        submitted_at=receipt.submitted_at.isoformat(),
    )


def _matches_managed_type(value: object, field_type: str) -> bool:
    if field_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if field_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if field_type in {"text", "date", "datetime", "select"}:
        return isinstance(value, str)
    if field_type == "boolean":
        return isinstance(value, bool)
    return True


@router.get("/submissions")
def list_submissions(request: Request) -> dict[str, object]:
    actor = require_mobile_actor(request)
    receipts = _services(request).electronic_integration.list_receipts(actor.user_id)
    return {
        "submissions": [
            {
                "submission_id": receipt.receipt_id,
                "form_id": receipt.form_id,
                "subject_employee_code": receipt.subject_employee_code,
                "status": receipt.status.value,
                "submitted_at": receipt.submitted_at.isoformat(),
                "idempotency_key": receipt.client_submission_id,
            }
            for receipt in receipts
        ]
    }
