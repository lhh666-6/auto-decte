"""Review lease, draft and disposition endpoints."""

from typing import NoReturn

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status

from app.api.dependencies_ds import get_current_actor, get_services
from app.api.routers.workbench_ds import build_workbench_response
from app.api.schemas.review_ds import (
    ConfirmAndClaimNextRequest,
    ConfirmRequest,
    ForceReleaseRequest,
    LeaseResponse,
    LeaseTokenRequest,
    ReviewActionRequest,
    SaveDraftRequest,
)
from app.modules.identity_access.models_ds import Actor, Permission
from app.modules.identity_access.policy_ds import PermissionPolicy
from app.modules.review.facade_ds import (
    ConfirmAndClaimNextCommand,
    ConfirmReviewCommand,
    ReviewDispositionCommand,
    SaveReviewDraftCommand,
)
from app.modules.review.models_ds import (
    LeaseHeldError,
    LeaseOwnershipError,
    ReviewRuleBlocked,
    ReviewVersionConflict,
)
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
    if services.repository.get_form(form_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "FORM_NOT_FOUND", "detail": f"Unknown form: {form_id}"},
        )
    try:
        lease = services.review_leases.acquire(form_id, actor.actor_id)
    except LeaseHeldError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "REVIEW_LEASE_HELD", "detail": str(error)},
        ) from error
    return LeaseResponse(
        form_id=lease.form_id,
        owner_id=lease.owner_id,
        lease_token=lease.lease_token,
        expires_at=lease.expires_at.isoformat(),
    )


@router.post("/{form_id}/review-lease/heartbeat", response_model=LeaseResponse)
def heartbeat_lease(
    form_id: str,
    body: LeaseTokenRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> LeaseResponse:
    actor = _actor(request, services)
    _require(actor, Permission.REVIEW_ACQUIRE)
    try:
        lease = services.review_leases.heartbeat(form_id, actor.actor_id, body.lease_token)
    except LeaseOwnershipError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "REVIEW_LEASE_NOT_OWNED", "detail": str(error)},
        ) from error
    return LeaseResponse(
        form_id=lease.form_id,
        owner_id=lease.owner_id,
        lease_token=lease.lease_token,
        expires_at=lease.expires_at.isoformat(),
    )


@router.delete("/{form_id}/review-lease", status_code=status.HTTP_204_NO_CONTENT)
def release_lease(
    form_id: str,
    body: LeaseTokenRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> Response:
    actor = _actor(request, services)
    _require(actor, Permission.REVIEW_ACQUIRE)
    try:
        services.review_leases.release(form_id, actor.actor_id, body.lease_token)
    except LeaseOwnershipError as error:
        raise HTTPException(
            status_code=409,
            detail={"code": "REVIEW_LEASE_NOT_OWNED", "detail": str(error)},
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{form_id}/review-lease/force-release", status_code=status.HTTP_204_NO_CONTENT)
def force_release_lease(
    form_id: str,
    body: ForceReleaseRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> Response:
    actor = _actor(request, services)
    _require(actor, Permission.REVIEW_FORCE_RELEASE)
    try:
        services.review_leases.force_release(form_id, actor.actor_id, body.reason)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail={"code": "REVIEW_REASON_REQUIRED", "detail": str(error)},
        ) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
    except (
        ReviewVersionConflict,
        LeaseOwnershipError,
        ReviewRuleBlocked,
        KeyError,
        ValueError,
    ) as error:
        _raise_workflow_error(error)
    return {"record_id": record.record_id, "version": record.version, "status": record.status.value}


@router.put("/{form_id}/review-draft")
def save_review_draft(
    form_id: str,
    body: SaveDraftRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = _actor(request, services)
    _require(actor, Permission.FORM_EDIT_DRAFT)
    try:
        draft = services.review_facade.save_draft(
            SaveReviewDraftCommand(
                form_id=form_id,
                expected_version=body.expected_version,
                values=body.values,
                actor_id=actor.actor_id,
                lease_token=body.lease_token,
                actor=actor,
            )
        )
    except (ReviewVersionConflict, LeaseOwnershipError, KeyError, ValueError) as error:
        _raise_workflow_error(error)
    return {
        "form_id": draft.form_id,
        "expected_version": draft.expected_version,
        "values": draft.values,
        "saved_by": draft.saved_by,
        "updated_at": draft.updated_at.isoformat(),
    }


@router.post("/{form_id}/return")
def return_form(
    form_id: str,
    body: ReviewActionRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = _actor(request, services)
    _require(actor, Permission.REVIEW_RETURN)
    try:
        review_status = services.review_facade.return_form(
            ReviewDispositionCommand(
                form_id=form_id,
                expected_version=body.expected_version,
                actor_id=actor.actor_id,
                lease_token=body.lease_token,
                reason=body.reason,
                evidence_ids=tuple(body.evidence_ids),
                actor=actor,
            )
        )
    except (ReviewVersionConflict, LeaseOwnershipError, KeyError, ValueError) as error:
        _raise_workflow_error(error)
    return {"form_id": form_id, "review_status": review_status.value}


@router.post("/{form_id}/void")
def void_form(
    form_id: str,
    body: ReviewActionRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = _actor(request, services)
    _require(actor, Permission.REVIEW_VOID)
    try:
        record = services.review_facade.void_form(
            ReviewDispositionCommand(
                form_id=form_id,
                expected_version=body.expected_version,
                actor_id=actor.actor_id,
                lease_token=body.lease_token,
                reason=body.reason,
                evidence_ids=tuple(body.evidence_ids),
                actor=actor,
            )
        )
    except (ReviewVersionConflict, LeaseOwnershipError, KeyError, ValueError) as error:
        _raise_workflow_error(error)
    return {"record_id": record.record_id, "version": record.version, "status": record.status.value}


@router.post("/{form_id}/confirm-and-claim-next")
def confirm_and_claim_next(
    form_id: str,
    body: ConfirmAndClaimNextRequest,
    request: Request,
    if_match: str | None = Header(default=None, alias="If-Match"),
    services: Services = Depends(get_services),  # noqa: B008
) -> dict[str, object]:
    actor = _actor(request, services)
    _require(
        actor,
        Permission.REVIEW_CONFIRM if body.expected_version == 0 else Permission.REVIEW_CORRECT,
    )
    expected_version = _expected_version(body.expected_version, if_match)
    try:
        result = services.review_facade.confirm_and_claim_next(
            ConfirmAndClaimNextCommand(
                form_id=form_id,
                expected_version=expected_version,
                values=body.values,
                actor_id=actor.actor_id,
                reason=body.reason,
                evidence_ids=tuple(body.evidence_ids),
                lease_token=body.lease_token,
                queue_key=body.queue_key,
                actor=actor,
            )
        )
    except (
        ReviewVersionConflict,
        LeaseOwnershipError,
        ReviewRuleBlocked,
        KeyError,
        ValueError,
    ) as error:
        _raise_workflow_error(error)
    next_context = None
    if result.next_form_id is not None and result.next_lease is not None:
        next_context = {
            "workbench": build_workbench_response(request, services, result.next_form_id),
            "lease": LeaseResponse(
                form_id=result.next_lease.form_id,
                owner_id=result.next_lease.owner_id,
                lease_token=result.next_lease.lease_token,
                expires_at=result.next_lease.expires_at.isoformat(),
            ),
        }
    return {
        "record": {
            "record_id": result.record.record_id,
            "version": result.record.version,
            "status": result.record.status.value,
        },
        "next": next_context,
    }


def _raise_workflow_error(error: Exception) -> NoReturn:
    if isinstance(error, ReviewVersionConflict):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "REVIEW_VERSION_CONFLICT",
                "submitted_version": error.submitted_version,
                "current_version": error.current_version,
            },
        ) from error
    if isinstance(error, LeaseOwnershipError):
        raise HTTPException(
            status_code=409,
            detail={"code": "REVIEW_LEASE_NOT_OWNED", "detail": str(error)},
        ) from error
    if isinstance(error, ReviewRuleBlocked):
        raise HTTPException(
            status_code=422,
            detail={
                "code": "REVIEW_RULE_BLOCKED",
                "detail": str(error),
                "failures": [
                    {
                        "code": failure.code,
                        "field_key": failure.field_key,
                        "message": failure.message,
                    }
                    for failure in error.failures
                ],
            },
        ) from error
    if isinstance(error, KeyError):
        raise HTTPException(
            status_code=404,
            detail={"code": "FORM_NOT_FOUND", "detail": str(error)},
        ) from error
    raise HTTPException(
        status_code=422,
        detail={"code": "INVALID_REVIEW_ACTION", "detail": str(error)},
    ) from error


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
