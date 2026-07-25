"""Quality Disposition API — Plant Manager final quality decisions.

V1 Business Rules:
- Inspector: submit inspection + evidence; CANNOT close exceptions
- Supervisor: provide opinion only; CANNOT close, CANNOT return
- Plant Manager: final disposition — responsible stage, person, A/B grade, signature

V1 Runtime Closure fixes:
- P0-01: Use require_web_actor (sync), not await get_current_actor (which is sync!)
- P0-03: factory_id and original_grade resolved SERVER-SIDE; client must NOT send them
- P0-04: GET endpoints enforce factory-scoped access
- P0-05: Full electronic signature snapshot returned in response
"""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from app.api.routers.web_auth_ds import require_web_actor, require_web_csrf
from app.application.quality_disposition_ds import QualityDispositionError
from app.modules.identity_access.web_policy_ds import WebWorkspace, allows_workspace

router = APIRouter(prefix="/api/v1/quality", tags=["Quality Disposition"])


# ── P0-03: Request body no longer accepts factory_id or original_grade ──
# The server resolves these authoritatively from the BambooRecord.


class CreateDispositionRequest(BaseModel):
    record_id: str = Field(..., description="Production record ID")
    inspection_id: str | None = Field(None)
    responsible_stage: str = Field(..., description="SORT / DIPPING / DRYING")
    effective_grade: str = Field(..., description="Final effective grade (A/B)")
    decision: str = Field(..., description="CONFIRMED / DOWNGRADED / UPGRADED")
    decision_note: str = Field(..., min_length=1, max_length=2000)


class UpdateDispositionRequest(BaseModel):
    effective_grade: str | None = Field(None)
    decision: str | None = Field(None)
    decision_note: str | None = Field(None, max_length=2000)


# ── P0-01 fix: use require_web_actor (sync) ──


def _require_plant_manager_or_admin(request: Request):
    """Authenticate and authorize: only PLANT_MANAGER or SYSTEM_ADMIN."""
    actor = require_web_actor(request)
    if not (
        allows_workspace(actor, WebWorkspace.PLANT)
        or allows_workspace(actor, WebWorkspace.ADMIN)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "QUALITY_DISPOSITION_FORBIDDEN",
                "detail": "仅厂长或管理员可进行质量处置",
            },
        )
    return actor


def _require_quality_read(request: Request):
    """Authenticate for read access. Returns actor for factory scoping."""
    actor = require_web_actor(request)
    # Plant Manager → scoped to own factory
    # Admin → global (factory_id=None means no filter)
    # Finance → read-only access
    # Others → 403
    if allows_workspace(actor, WebWorkspace.ADMIN):
        return actor, None  # Admin: global access
    if allows_workspace(actor, WebWorkspace.PLANT):
        return actor, actor.factory_id  # Plant Manager: own factory only
    if allows_workspace(actor, WebWorkspace.FINANCE):
        return actor, actor.factory_id  # Finance: own factory only
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "QUALITY_READ_FORBIDDEN",
            "detail": "当前角色无权查看质量处置记录",
        },
    )


def _services(request: Request):
    return request.app.state.services


# ── POST /dispositions ─────────────────────────────────────────────


@router.post("/dispositions")
def create_disposition(
    body: CreateDispositionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict:
    actor = _require_plant_manager_or_admin(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _services(request).quality_disposition.create_disposition(
            record_id=body.record_id,
            inspection_id=body.inspection_id,
            responsible_stage=body.responsible_stage,
            effective_grade=body.effective_grade,
            decision=body.decision,
            decision_note=body.decision_note,
            decided_by=actor.employee_code,
            decided_by_name=actor.employee_name,
            decided_by_factory=actor.factory_id,
            decided_by_position=actor.primary_role.value
            if actor.primary_role
            else "",
        )
    except QualityDispositionError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": error.code, "detail": error.detail},
        ) from error


# ── GET /dispositions/{record_id} ───────────────────────────────────


@router.get("/dispositions/{record_id}")
def get_disposition(
    record_id: str,
    request: Request,
) -> dict:
    actor, scoped_factory = _require_quality_read(request)
    result = _services(request).quality_disposition.get_disposition(
        record_id, actor_factory_id=scoped_factory
    )
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Disposition not found",
        )
    return result


# ── GET /dispositions ───────────────────────────────────────────────


@router.get("/dispositions")
def list_dispositions(
    request: Request,
    factory_id: str = Query(..., description="Factory ID to query"),
    limit: int = Query(50, ge=1, le=200),
) -> dict:
    actor, scoped_factory = _require_quality_read(request)
    # P0-04: Plant Manager can only see own factory
    effective_factory = scoped_factory if scoped_factory is not None else factory_id
    items = _services(request).quality_disposition.list_dispositions(
        effective_factory, limit=limit
    )
    return {"items": items}


# ── PATCH /dispositions/{record_id} ─────────────────────────────────


@router.patch("/dispositions/{record_id}")
def update_disposition(
    record_id: str,
    body: UpdateDispositionRequest,
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
) -> dict:
    actor = _require_plant_manager_or_admin(request)
    require_web_csrf(request, x_csrf_token)
    try:
        return _services(request).quality_disposition.update_disposition(
            record_id,
            effective_grade=body.effective_grade,
            decision=body.decision,
            decision_note=body.decision_note,
            decided_by=actor.employee_code,
            decided_by_name=actor.employee_name,
            decided_by_factory=actor.factory_id,
            decided_by_position=actor.primary_role.value
            if actor.primary_role
            else "",
        )
    except QualityDispositionError as error:
        status_code = (
            status.HTTP_404_NOT_FOUND
            if error.code == "DISPOSITION_NOT_FOUND"
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(
            status_code=status_code,
            detail={"code": error.code, "detail": error.detail},
        ) from error
