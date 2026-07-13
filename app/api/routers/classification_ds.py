"""Controlled fallback when a paper form's template QR cannot be read."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.dependencies_ds import get_current_actor, get_services
from app.domain.models import ReviewStatus
from app.domain.templates_ds import TemplateStatus
from app.modules.identity_access.models_ds import Actor, Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.services.container import Services

router = APIRouter(prefix="/api/v1/forms", tags=["classification"])


class AssignTemplateRequest(BaseModel):
    """A deliberate operator classification; this never accepts a storage path."""

    template_key: str = Field(pattern=r"^[A-Z0-9_]+$")
    version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=500)


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


@router.post("/{form_id}/assign-template")
def assign_template(
    form_id: str,
    body: AssignTemplateRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    """Bind an unclassified form to a published template and audit the decision."""
    actor = _actor(request, services)
    _require(actor, Permission.FORM_CLASSIFY)
    form = services.repository.get_form(form_id)
    if form is None:
        raise HTTPException(status_code=404, detail={"code": "FORM_NOT_FOUND"})
    if form.review_status is not ReviewStatus.NEEDS_CLASSIFICATION:
        raise HTTPException(
            status_code=409,
            detail={"code": "FORM_NOT_AWAITING_CLASSIFICATION"},
        )
    template = services.template_repository.get_version_by_key_version(
        body.template_key, body.version
    )
    if template is None or template.status is not TemplateStatus.PUBLISHED:
        raise HTTPException(
            status_code=422,
            detail={"code": "TEMPLATE_VERSION_NOT_PUBLISHED"},
        )
    services.recognition.manual_reclassify(
        form_id=form_id,
        template_id=template.template_key,
        template_version=str(template.version),
        actor_id=actor.actor_id,
        reason=body.reason,
    )
    return {
        "form_id": form_id,
        "template_key": template.template_key,
        "template_version": template.version,
        "review_status": ReviewStatus.CLASSIFIED.value,
    }
