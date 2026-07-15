"""Authorized template draft, publication and printable-artifact endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from pydantic import Field as PydanticField

from app.api.dependencies_ds import get_current_actor, get_services
from app.application.template_versions_ds import PreflightReport
from app.domain.templates_ds import (
    ExportTarget,
    FieldDefinition,
    FieldRules,
    PageSpec,
    Rect,
    TemplateArtifact,
    TemplateStatus,
    TemplateVersion,
)
from app.modules.identity_access.models_ds import Actor, Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.services.container import Services

router = APIRouter(prefix="/api/v1", tags=["templates"])


class CreateTemplateRequest(BaseModel):
    template_key: str
    page_size: str = "A4"


class RegionRequest(BaseModel):
    x: float
    y: float
    width: float
    height: float


class FieldRulesRequest(BaseModel):
    required: bool = False
    minimum_value: float | None = None
    maximum_value: float | None = None
    allowed_values: list[str] = PydanticField(default_factory=list)
    master_data_source: str | None = None
    allow_exception_reason: bool = False


class ExportTargetRequest(BaseModel):
    workbook: str = "records.xlsx"
    worksheet: str = "records"
    business_column: str | None = None


class FieldRequest(BaseModel):
    field_key: str
    display_name: str
    data_type: str
    input_type: str
    region: RegionRequest
    recognition_engine: str = "manual"
    minimum_prefill_confidence: float = 1.0
    rules: FieldRulesRequest = PydanticField(default_factory=FieldRulesRequest)
    export_target: ExportTargetRequest = PydanticField(default_factory=ExportTargetRequest)


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


@router.post("/templates", status_code=status.HTTP_201_CREATED)
def create_template(
    body: CreateTemplateRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    page = _page_spec(body.page_size)
    version = services.templates.create_draft(body.template_key, page)
    return _version_payload(version, ())


@router.post("/template-versions/{version_id}/fields")
def add_field(
    version_id: str,
    body: FieldRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    try:
        version = services.templates.get(version_id)
        updated = services.templates.add_field(version_id, _field_definition(body, version.page))
    except KeyError as error:
        raise _version_not_found(error) from error
    except ValueError as error:
        raise _invalid_field(error) from error
    return _version_payload(updated, ())


@router.post("/template-versions/{version_id}/preflight")
def preflight(
    version_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    try:
        report = services.templates.preflight(version_id)
        version = services.templates.get(version_id)
    except KeyError as error:
        raise _version_not_found(error) from error
    return _preflight_payload(report, version)


@router.post("/template-versions/{version_id}/publish")
def publish(
    version_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    try:
        version = services.templates.publish(version_id)
    except KeyError as error:
        raise _version_not_found(error) from error
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_LIFECYCLE", "detail": str(error)},
        ) from error
    artifacts = services.template_renderer.render(version)
    for artifact in artifacts:
        services.template_repository.add_artifact(artifact)
    return _version_payload(version, artifacts)


@router.get("/templates")
def list_templates(
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> list[dict[str, object]]:
    _require(_actor(request, services), Permission.TEMPLATE_READ)
    versions = services.templates.list_templates()
    summaries: list[dict[str, object]] = []
    for template_key in sorted({version.template_key for version in versions}):
        candidates = [version for version in versions if version.template_key == template_key]
        published = [
            version for version in candidates if version.status is TemplateStatus.PUBLISHED
        ]
        editable = [
            version for version in candidates
            if version.status in {
                TemplateStatus.DRAFT,
                TemplateStatus.PREFLIGHT_FAILED,
                TemplateStatus.READY_TO_PUBLISH,
            }
        ]
        selected = max(published or candidates, key=lambda item: (item.version, item.version_id))
        active_draft = max(editable, key=lambda item: (item.version, item.version_id), default=None)
        summaries.append(_library_item_payload(selected, active_draft))
    return summaries


@router.get("/template-versions/{version_id}")
def get_template_version(
    version_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_READ)
    try:
        version = services.templates.get(version_id)
    except KeyError as error:
        raise _version_not_found(error) from error
    return _version_payload(version, services.template_repository.list_artifacts(version_id))


@router.post("/template-versions/{version_id}/clone", status_code=status.HTTP_201_CREATED)
def clone_template_version(
    version_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    try:
        version = services.templates.clone(version_id)
    except KeyError as error:
        raise _version_not_found(error) from error
    except ValueError as error:
        raise _invalid_lifecycle(error) from error
    return _version_payload(version, ())


@router.patch("/template-versions/{version_id}/fields/{field_key}")
def replace_field(
    version_id: str,
    field_key: str,
    body: FieldRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    try:
        version = services.templates.get(version_id)
    except KeyError as error:
        raise _version_not_found(error) from error
    try:
        updated = services.templates.replace_field(
            version_id, field_key, _field_definition(body, version.page)
        )
    except KeyError as error:
        raise _field_not_found(error) from error
    except ValueError as error:
        if "cannot be mutated" in str(error):
            raise _invalid_lifecycle(error) from error
        raise _invalid_field(error) from error
    return _version_payload(updated, ())


@router.delete("/template-versions/{version_id}/fields/{field_key}")
def delete_field(
    version_id: str,
    field_key: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    try:
        services.templates.get(version_id)
    except KeyError as error:
        raise _version_not_found(error) from error
    try:
        updated = services.templates.remove_field(version_id, field_key)
    except KeyError as error:
        raise _field_not_found(error) from error
    except ValueError as error:
        if "cannot be mutated" in str(error):
            raise _invalid_lifecycle(error) from error
        raise _invalid_field(error) from error
    return _version_payload(updated, ())


@router.get("/template-artifacts/{artifact_id}/content")
def download_artifact(
    artifact_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> FileResponse:
    _require(_actor(request, services), Permission.TEMPLATE_READ)
    artifact = services.template_repository.get_artifact(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail={"code": "ARTIFACT_NOT_FOUND"})
    path = _safe_artifact_path(artifact, services.settings.evidence_root)
    return FileResponse(path, filename=artifact.download_name)


def _page_spec(page_size: str) -> PageSpec:
    if page_size == "A4":
        return PageSpec.a4_portrait()
    if page_size == "A5":
        return PageSpec.a5_portrait()
    raise HTTPException(status_code=422, detail={"code": "INVALID_PAGE_SIZE"})


def _field_definition(body: FieldRequest, page: PageSpec) -> FieldDefinition:
    return FieldDefinition(
        body.field_key,
        body.display_name,
        body.data_type,
        body.input_type,
        Rect(body.region.x, body.region.y, body.region.width, body.region.height),
        page,
        body.recognition_engine,
        body.minimum_prefill_confidence,
        FieldRules(
            required=body.rules.required,
            minimum_value=body.rules.minimum_value,
            maximum_value=body.rules.maximum_value,
            allowed_values=tuple(body.rules.allowed_values),
            master_data_source=body.rules.master_data_source,
            allow_exception_reason=body.rules.allow_exception_reason,
        ),
        ExportTarget(
            body.export_target.workbook,
            body.export_target.worksheet,
            body.export_target.business_column or body.field_key,
        ),
    )


def _version_not_found(error: KeyError) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "TEMPLATE_VERSION_NOT_FOUND", "detail": str(error)},
    )


def _field_not_found(error: KeyError) -> HTTPException:
    return HTTPException(
        status_code=404,
        detail={"code": "FIELD_NOT_FOUND", "detail": str(error)},
    )


def _invalid_lifecycle(error: ValueError) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={"code": "INVALID_LIFECYCLE", "detail": str(error)},
    )


def _invalid_field(error: ValueError) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={"code": "INVALID_FIELD", "detail": str(error)},
    )


def _safe_artifact_path(artifact: TemplateArtifact, evidence_root: Path) -> Path:
    root = (evidence_root / "template-artifacts").resolve()
    path = Path(artifact.internal_uri).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail={"code": "ARTIFACT_NOT_FOUND"})
    return path


def _preflight_payload(report: PreflightReport, version: TemplateVersion) -> dict[str, object]:
    return {
        "ok": report.ok,
        "status": version.status.value,
        "issues": [{"code": issue.code, "detail": issue.detail} for issue in report.issues],
    }


def _version_payload(
    version: TemplateVersion,
    artifacts: tuple[TemplateArtifact, ...] | list[TemplateArtifact],
) -> dict[str, object]:
    return {
        "version_id": version.version_id,
        "template_key": version.template_key,
        "version": version.version,
        "status": version.status.value,
        "parent_version_id": version.parent_version_id,
        "page": _page_payload(version.page),
        "fields": [
            {
                "field_key": field.field_key,
                "display_name": field.display_name,
                "data_type": field.data_type,
                "input_type": field.input_type,
                "recognition_engine": field.recognition_engine,
                "minimum_prefill_confidence": field.minimum_prefill_confidence,
                "rules": {
                    "required": field.rules.required,
                    "minimum_value": field.rules.minimum_value,
                    "maximum_value": field.rules.maximum_value,
                    "allowed_values": list(field.rules.allowed_values),
                    "master_data_source": field.rules.master_data_source,
                    "allow_exception_reason": field.rules.allow_exception_reason,
                },
                "export_target": (
                    {
                        "workbook": field.export_target.workbook,
                        "worksheet": field.export_target.worksheet,
                        "business_column": field.export_target.business_column,
                    }
                    if field.export_target is not None
                    else None
                ),
                "region": {
                    "x": field.region.x,
                    "y": field.region.y,
                    "width": field.region.width,
                    "height": field.region.height,
                },
            }
            for field in version.fields
        ],
        "artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "kind": artifact.kind,
                "download_name": artifact.download_name,
                "sha256": artifact.sha256,
                "download_url": f"/api/v1/template-artifacts/{artifact.artifact_id}/content",
            }
            for artifact in artifacts
        ],
    }


def _library_item_payload(
    version: TemplateVersion, active_draft: TemplateVersion | None = None
) -> dict[str, object]:
    return {
        "template_key": version.template_key,
        "version_id": version.version_id,
        "current_published_version": (
            version.version if version.status.value == "PUBLISHED" else None
        ),
        "version": version.version,
        "status": version.status.value,
        "page": _page_payload(version.page),
        "field_count": len(version.fields),
        "active_draft": (
            {
                "version_id": active_draft.version_id,
                "version": active_draft.version,
                "status": active_draft.status.value,
                "field_count": len(active_draft.fields),
            }
            if active_draft is not None
            else None
        ),
    }


def _page_payload(page: PageSpec) -> dict[str, object]:
    return {
        "size": page.size,
        "orientation": page.orientation,
        "width_mm": page.width_mm,
        "height_mm": page.height_mm,
        "canonical_dpi": page.canonical_dpi,
        "canonical_width_px": page.canonical_width_px,
        "canonical_height_px": page.canonical_height_px,
    }
