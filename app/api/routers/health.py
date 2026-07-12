"""Liveness and readiness endpoints."""

from fastapi import APIRouter, Depends

from app.api.dependencies import get_services
from app.services.container import Services

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live")
def live() -> dict[str, str]:
    return {"status": "live"}


@router.get("/ready")
def ready(services: Services = Depends(get_services)) -> dict[str, object]:  # noqa: B008
    services.settings.evidence_root.mkdir(parents=True, exist_ok=True)
    services.repository.list_export_batches()
    return {
        "status": "ready",
        "capabilities": {
            "ai": services.settings.ai_enabled,
            "vector": True,
            "audio_transcription": False,
        },
    }
