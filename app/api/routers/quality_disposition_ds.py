"""Quality Disposition API — Plant Manager final quality decisions.

V1 Business Rules:
- Inspector: submit inspection + evidence; CANNOT close exceptions
- Supervisor: provide opinion only; CANNOT close, CANNOT return
- Plant Manager: final disposition — responsible stage, person, A/B grade, signature
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.api.dependencies_ds import get_current_actor, get_services
from app.application.quality_disposition_ds import QualityDispositionError
from app.modules.bamboo_process.models_ds import BambooRole
from app.services.container import Services

router = APIRouter(prefix="/api/v1/quality", tags=["Quality Disposition"])


class CreateDispositionRequest(BaseModel):
    record_id: str = Field(..., description="Production record ID")
    inspection_id: str | None = Field(None)
    factory_id: str = Field(...)
    responsible_stage: str = Field(..., description="SORT / DIPPING / DRYING")
    original_grade: str = Field(..., description="Original grade from production")
    effective_grade: str = Field(..., description="Final effective grade (A/B)")
    decision: str = Field(..., description="CONFIRMED / DOWNGRADED / etc.")
    decision_note: str = Field("", max_length=2000)


class UpdateDispositionRequest(BaseModel):
    effective_grade: str | None = Field(None)
    decision: str | None = Field(None)
    decision_note: str | None = Field(None, max_length=2000)


def _require_plant_manager_or_admin(actor) -> None:
    if actor.role not in {BambooRole.PLANT_MANAGER, BambooRole.SYSTEM_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "QUALITY_DISPOSITION_FORBIDDEN",
                "detail": "仅厂长或管理员可进行质量处置",
            },
        )


@router.post("/dispositions")
async def create_disposition(
    body: CreateDispositionRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict:
    actor = await get_current_actor(request, services)
    _require_plant_manager_or_admin(actor)
    try:
        return services.quality_disposition.create_disposition(
            record_id=body.record_id,
            inspection_id=body.inspection_id,
            factory_id=body.factory_id,
            responsible_stage=body.responsible_stage,
            original_grade=body.original_grade,
            effective_grade=body.effective_grade,
            decision=body.decision,
            decision_note=body.decision_note,
            decided_by=actor.employee_code,
        )
    except QualityDispositionError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": error.code, "detail": error.detail},
        ) from error


@router.get("/dispositions/{record_id}")
async def get_disposition(
    record_id: str,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict | None:
    result = services.quality_disposition.get_disposition(record_id)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Disposition not found")
    return result


@router.get("/dispositions")
async def list_dispositions(
    factory_id: str,
    limit: int = 50,
    services: Services = Depends(get_services),  # noqa: B008
) -> list[dict]:
    return services.quality_disposition.list_dispositions(factory_id, limit=limit)


@router.patch("/dispositions/{record_id}")
async def update_disposition(
    record_id: str,
    body: UpdateDispositionRequest,
    request: Request,
    services: Services = Depends(get_services),  # noqa: B008
) -> dict:
    actor = await get_current_actor(request, services)
    _require_plant_manager_or_admin(actor)
    try:
        return services.quality_disposition.update_disposition(
            record_id,
            effective_grade=body.effective_grade,
            decision=body.decision,
            decision_note=body.decision_note,
            decided_by=actor.employee_code,
        )
    except QualityDispositionError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": error.code, "detail": error.detail},
        ) from error
