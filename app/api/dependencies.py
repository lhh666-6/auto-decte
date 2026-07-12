"""FastAPI dependencies for the modular monolith."""

from fastapi import Request

from app.modules.identity_access.local import LocalIdentityProvider
from app.modules.identity_access.models import Actor
from app.services.container import Services


def get_services(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


def get_current_actor(services: Services) -> Actor:
    return LocalIdentityProvider(
        services.settings.local_default_user_id,
        services.settings.local_default_roles,
    ).current_actor()
