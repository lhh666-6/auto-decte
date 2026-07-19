"""Read endpoints used by the React human review workbench."""

from enum import Enum
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app.api.dependencies_ds import get_current_actor, get_services
from app.api.schemas.workbench import (
    AuditEventResponse,
    CandidateResponse,
    EvidenceResponse,
    FieldResponse,
    FieldRulesResponse,
    FormSummaryResponse,
    MasterDataOptionResponse,
    RecordVersionResponse,
    ReviewDraftResponse,
    ReviewHistoryResponse,
    WorkbenchDetailResponse,
)
from app.application.query_forms import FormWorkbench
from app.domain.models import (
    EvidenceFile,
    EvidenceType,
    ExportStatus,
    RecordStatus,
    RecordVersion,
    ReviewStatus,
    ValueSource,
)
from app.modules.identity_access.models_ds import Actor, Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.services.container import Services

router = APIRouter(prefix="/api/v1/forms", tags=["review-workbench"])


def _enum_value(value: Enum | None) -> str | None:
    return str(value.value) if value is not None else None


def _actor(request: Request, services: Services) -> Actor:
    return get_current_actor(request, services)


def _require(actor: Actor, permission: Permission) -> None:
    try:
        PermissionPolicy().require(actor, permission)
    except PermissionError as error:
        raise HTTPException(
            status_code=403,
            detail={"code": "PERMISSION_DENIED", "detail": str(error)},
        ) from error


def _workbench_or_404(services: Services, form_id: str) -> FormWorkbench:
    try:
        return services.queries.workbench(form_id)
    except KeyError as error:
        raise HTTPException(
            status_code=404,
            detail={"code": "FORM_NOT_FOUND", "detail": f"Unknown form: {form_id}"},
        ) from error


def _record_response(record: RecordVersion) -> RecordVersionResponse:
    return RecordVersionResponse(
        record_id=record.record_id,
        version=record.version,
        previous_version=record.previous_version,
        status=record.status.value,
        values=record.values,
        change_reason=record.change_reason,
        confirmed_by=record.confirmed_by,
        created_at=record.created_at,
    )


_QUEUE_FILTERS: dict[str, tuple[tuple[ReviewStatus, ...], tuple[ExportStatus, ...]]] = {
    "classification": ((ReviewStatus.NEEDS_CLASSIFICATION,), ()),
    "review": (
        (
            ReviewStatus.IMPORTED,
            ReviewStatus.CLASSIFIED,
            ReviewStatus.RECOGNIZED,
            ReviewStatus.NEEDS_REVIEW,
        ),
        (),
    ),
    "exceptions": ((ReviewStatus.RECAPTURE_REQUIRED,), ()),
    "exportable": (
        (ReviewStatus.CONFIRMED, ReviewStatus.CORRECTED),
        (ExportStatus.NOT_EXPORTED, ExportStatus.REEXPORT_REQUIRED),
    ),
}


@router.get("/queue/{queue_key}", response_model=list[FormSummaryResponse])
def get_queue(
    queue_key: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> list[FormSummaryResponse]:
    """Return a real queue, including forms without a record version yet."""
    actor = _actor(request, services)
    _require(actor, Permission.FORM_READ)
    filters = _QUEUE_FILTERS.get(queue_key)
    if filters is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "QUEUE_NOT_FOUND", "detail": f"Unknown queue: {queue_key}"},
        )
    forms = services.queries.list_forms(review_statuses=filters[0], export_statuses=filters[1])
    return [
        FormSummaryResponse(
            form_id=form.form_id,
            template_id=form.template_id,
            template_version=form.template_version,
            coordinate_version=form.coordinate_version,
            review_status=form.review_status.value,
            export_status=form.export_status.value,
            current_record_version=form.current_record_version,
            priority=form.priority,
            created_at=form.created_at,
        )
        for form in forms
    ]


@router.get("/{form_id}", response_model=WorkbenchDetailResponse)
def get_workbench_detail(
    form_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> WorkbenchDetailResponse:
    actor = _actor(request, services)
    _require(actor, Permission.FORM_READ)
    return build_workbench_response(request, services, form_id)


def build_workbench_response(
    request: Request, services: Services, form_id: str
) -> WorkbenchDetailResponse:
    """Build the reusable workbench DTO for reads and atomic next responses."""
    workbench = _workbench_or_404(services, form_id)
    attempts_by_field: dict[str, list[CandidateResponse]] = {}
    for attempt in workbench.trace.attempts:
        attempts_by_field.setdefault(attempt.field_id, []).append(
            CandidateResponse(
                attempt_id=attempt.attempt_id,
                candidate_value=attempt.candidate_value,
                confidence=attempt.confidence,
                engine=attempt.engine,
                model_version=attempt.model_version,
                crop_file_id=attempt.crop_file_id,
            )
        )
    form = workbench.trace.form
    draft = services.review_repository.get_draft(form_id)
    try:
        template = services.template_repository.get_version_by_key_version(
            form.template_id, int(form.template_version)
        )
    except ValueError:
        template = None
    template_fields = (
        {field.field_key: field for field in template.fields} if template is not None else {}
    )
    latest_record = workbench.trace.versions[-1] if workbench.trace.versions else None
    confirmed_values_by_field_id: dict[str, object] = {}
    if latest_record is not None and latest_record.status in {
        RecordStatus.CONFIRMED,
        RecordStatus.CORRECTED,
    }:
        for field in workbench.fields:
            if field.field_name in latest_record.values:
                confirmed_values_by_field_id[field.field_id] = latest_record.values[
                    field.field_name
                ]
            elif field.field_id in latest_record.values:
                confirmed_values_by_field_id[field.field_id] = latest_record.values[field.field_id]
    master_data_options: dict[str, list[dict[str, str]]] = {}
    for definition in template_fields.values():
        source = definition.rules.master_data_source
        if source and source not in master_data_options:
            master_data_options[source] = services.master_data.options(source)
    return WorkbenchDetailResponse(
        form=FormSummaryResponse(
            form_id=form.form_id,
            template_id=form.template_id,
            template_version=form.template_version,
            coordinate_version=form.coordinate_version,
            review_status=form.review_status.value,
            export_status=form.export_status.value,
            current_record_version=form.current_record_version,
            priority=form.priority,
            created_at=form.created_at,
        ),
        fields=[
            FieldResponse(
                field_id=field.field_id,
                field_name=field.field_name,
                display_name=(
                    template_fields[field.field_name].display_name
                    if field.field_name in template_fields
                    else None
                ),
                data_type=(
                    template_fields[field.field_name].data_type
                    if field.field_name in template_fields
                    else None
                ),
                recognition_engine=(
                    template_fields[field.field_name].recognition_engine
                    if field.field_name in template_fields
                    else None
                ),
                paper_entry_mode=_enum_value(
                    template_fields[field.field_name].paper_entry_mode
                    if field.field_name in template_fields
                    else None
                ),
                recognition_mode=_enum_value(
                    template_fields[field.field_name].recognition_mode
                    if field.field_name in template_fields
                    else None
                ),
                fill_policy=_enum_value(
                    template_fields[field.field_name].fill_policy
                    if field.field_name in template_fields
                    else None
                ),
                requires_manual_confirmation=(
                    template_fields[field.field_name].requires_manual_confirmation
                    if field.field_name in template_fields
                    else False
                ),
                rules=(
                    FieldRulesResponse(
                        required=template_fields[field.field_name].rules.required,
                        minimum_value=(template_fields[field.field_name].rules.minimum_value),
                        maximum_value=(template_fields[field.field_name].rules.maximum_value),
                        allowed_values=list(template_fields[field.field_name].rules.allowed_values),
                        master_data_source=(
                            template_fields[field.field_name].rules.master_data_source
                        ),
                        master_data_options=[
                            MasterDataOptionResponse(**option)
                            for option in master_data_options.get(
                                template_fields[field.field_name].rules.master_data_source or "",
                                [],
                            )
                        ],
                    )
                    if field.field_name in template_fields
                    else None
                ),
                source_region=field.source_region,
                current_value=(
                    confirmed_values_by_field_id[field.field_id]
                    if field.field_id in confirmed_values_by_field_id
                    else field.current_value
                ),
                current_value_source=(
                    ValueSource.HUMAN_CONFIRMED.value
                    if field.field_id in confirmed_values_by_field_id
                    else field.current_value_source.value
                    if field.current_value_source
                    else None
                ),
                current_record_version=(
                    latest_record.version
                    if field.field_id in confirmed_values_by_field_id and latest_record is not None
                    else field.current_record_version
                ),
                candidates=attempts_by_field.get(field.field_id, []),
            )
            for field in workbench.fields
        ],
        evidence=[
            _evidence_response(request, form_id, evidence) for evidence in workbench.trace.evidence
        ],
        current_record=(
            _record_response(workbench.trace.versions[-1]) if workbench.trace.versions else None
        ),
        draft=(
            ReviewDraftResponse(
                expected_version=draft.expected_version,
                values=draft.values,
                saved_by=draft.saved_by,
                updated_at=draft.updated_at,
            )
            if draft is not None
            else None
        ),
    )


@router.get("/{form_id}/review-history", response_model=ReviewHistoryResponse)
def get_review_history(
    form_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> ReviewHistoryResponse:
    actor = _actor(request, services)
    _require(actor, Permission.AUDIT_READ)
    trace = _workbench_or_404(services, form_id).trace
    return ReviewHistoryResponse(
        versions=[_record_response(version) for version in trace.versions],
        audits=[
            AuditEventResponse(
                event_id=event.event_id,
                event_type=event.event_type,
                actor_id=event.actor_id,
                timestamp=event.timestamp,
                reason=event.reason,
                evidence_ids=list(event.evidence_ids),
            )
            for event in trace.audits
        ],
    )


@router.get("/{form_id}/evidence/{file_id}", name="read_evidence")
def read_evidence(
    form_id: str,
    file_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> FileResponse:
    actor = _actor(request, services)
    _require(actor, Permission.FORM_READ)
    evidence = next(
        (
            item
            for item in _workbench_or_404(services, form_id).trace.evidence
            if item.file_id == file_id
        ),
        None,
    )
    if evidence is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "EVIDENCE_NOT_FOUND", "detail": f"Unknown evidence: {file_id}"},
        )
    _require(
        actor,
        (
            Permission.EVIDENCE_AUDIO_READ
            if evidence.type is EvidenceType.AUDIO
            else Permission.EVIDENCE_IMAGE_READ
        ),
    )
    path = _evidence_path(services, evidence)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail={
                "code": "EVIDENCE_UNAVAILABLE",
                "detail": f"Evidence file unavailable: {file_id}",
            },
        )
    return FileResponse(path, filename=path.name)


def _evidence_response(request: Request, form_id: str, evidence: EvidenceFile) -> EvidenceResponse:
    return EvidenceResponse(
        file_id=evidence.file_id,
        type=evidence.type.value,
        related_field_id=evidence.related_field_id,
        sha256=evidence.sha256,
        immutable=evidence.immutable,
        created_at=evidence.created_at,
        download_url=f"/api/v1/forms/{form_id}/evidence/{evidence.file_id}",
    )


def _evidence_path(services: Services, evidence: EvidenceFile) -> Path:
    root = services.settings.evidence_root.resolve()
    path = (root / evidence.uri).resolve()
    if not path.is_relative_to(root):
        raise HTTPException(
            status_code=404,
            detail={"code": "EVIDENCE_UNAVAILABLE", "detail": "Evidence path is invalid."},
        )
    return path
