"""Authorized template draft, publication and printable-artifact endpoints."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.api.dependencies_ds import get_current_actor, get_services
from app.application.template_versions_ds import PreflightReport
from app.domain.templates_ds import (
    FieldDefinition,
    PageSpec,
    Rect,
    TemplateArtifact,
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
    x: float = Field(ge=0, lt=1)
    y: float = Field(ge=0, lt=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)


class AddFieldRequest(BaseModel):
    field_key: str
    display_name: str
    data_type: str
    input_type: str
    region: RegionRequest


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
    body: AddFieldRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    version = services.templates.get(version_id)
    region = Rect(body.region.x, body.region.y, body.region.width, body.region.height)
    try:
        updated = services.templates.add_field(
            version_id,
            FieldDefinition(
                body.field_key,
                body.display_name,
                body.data_type,
                body.input_type,
                region,
                version.page,
            ),
        )
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_FIELD", "detail": str(error)},
        ) from error
    return _version_payload(updated, ())


@router.post("/template-versions/{version_id}/preflight")
def preflight(
    version_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    _require(_actor(request, services), Permission.TEMPLATE_CREATE_VERSION)
    report = services.templates.preflight(version_id)
    version = services.templates.get(version_id)
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
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "INVALID_LIFECYCLE", "detail": str(error)},
        ) from error
    artifacts = services.template_renderer.render(version)
    for artifact in artifacts:
        services.template_repository.add_artifact(artifact)
    return _version_payload(version, artifacts)


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
        "fields": [field.field_key for field in version.fields],
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
