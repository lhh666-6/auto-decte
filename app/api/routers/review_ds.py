"""Review lease and confirmation endpoints."""

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.api.dependencies_ds import get_current_actor, get_services
from app.api.schemas.review_ds import ConfirmRequest, LeaseResponse
from app.modules.identity_access.models_ds import Actor, Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.modules.review.facade_ds import ConfirmReviewCommand
from app.modules.review.models_ds import ReviewVersionConflict
from app.services.container import Services

router = APIRouter(prefix="/api/v1/forms", tags=["review"])


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


@router.post("/{form_id}/review-lease", response_model=LeaseResponse)
def acquire_lease(
    form_id: str,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> LeaseResponse:
    actor = _actor(request, services)
    _require(actor, Permission.REVIEW_ACQUIRE)
    lease = services.review_leases.acquire(form_id, actor.actor_id)
    return LeaseResponse(
        form_id=lease.form_id,
        owner_id=lease.owner_id,
        lease_token=lease.lease_token,
        expires_at=lease.expires_at.isoformat(),
    )


@router.post("/{form_id}/confirm")
def confirm(
    form_id: str,
    body: ConfirmRequest,
    request: Request,
    if_match: str | None = Header(default=None, alias="If-Match"),
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = _actor(request, services)
    _require(actor, Permission.REVIEW_CONFIRM)
    expected_version = _expected_version(body.expected_version, if_match)
    try:
        record = services.review_facade.confirm(
            ConfirmReviewCommand(
                form_id=form_id,
                expected_version=expected_version,
                values=body.values,
                actor_id=actor.actor_id,
                reason=body.reason,
                evidence_ids=tuple(body.evidence_ids),
                actor=actor,
                lease_token=body.lease_token,
            )
        )
    except ReviewVersionConflict as error:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "REVIEW_VERSION_CONFLICT",
                "submitted_version": error.submitted_version,
                "current_version": error.current_version,
            },
        ) from error
    return {"record_id": record.record_id, "version": record.version, "status": record.status.value}


def _expected_version(body_version: int, if_match: str | None) -> int:
    if if_match is None:
        return body_version
    try:
        return int(if_match.strip().strip('"'))
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_IF_MATCH",
                "detail": "If-Match must contain an integer version.",
            },
        ) from error
