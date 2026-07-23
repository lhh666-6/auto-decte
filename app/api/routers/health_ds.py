"""Liveness and readiness endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy import text

from app.api.dependencies_ds import get_services
from app.services.container import Services

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/ready")
def ready(services: Services = Depends(get_services)) -> dict[str, object]:  # noqa: B008
    services.settings.evidence_root.mkdir(parents=True, exist_ok=True)
    with services.engine.connect() as connection:
        connection.execute(text("SELECT 1")).scalar_one()
    return {
        "status": "ready",
        "capabilities": {
            "ai": services.settings.ai_enabled,
            "vector": True,
            "audio_transcription": False,
        },
    }
