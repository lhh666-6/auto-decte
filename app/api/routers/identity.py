"""Current local identity endpoint."""

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_current_actor, get_services
from app.modules.identity_access.models import Actor
from app.services.container import Services

router = APIRouter(prefix="/api/v1", tags=["identity"])


@router.get("/me")
def me(request: Request, services: Services = Depends(get_services)) -> dict[str, object]:  # noqa: B008
    actor: Actor = get_current_actor(request, services)
    return {"actor_id": actor.actor_id, "roles": sorted(role.value for role in actor.roles)}
