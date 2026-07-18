"""FastAPI dependencies for the modular monolith."""

from fastapi import Request

from app.modules.identity_access.local_ds import LocalIdentityProvider
from app.modules.identity_access.models_ds import Actor
from app.services.container import Services


def get_services(request: Request) -> Services:
    return request.app.state.services  # type: ignore[no-any-return]


def get_current_actor(request: Request, services: Services) -> Actor:
    if not services.settings.allow_header_identity:
        return LocalIdentityProvider(
            services.settings.local_default_user_id,
            services.settings.local_default_roles,
            full_access=services.settings.app_auth_mode == "local_full_access",
        ).current_actor()
    has_explicit_identity = "X-Actor-ID" in request.headers or "X-Roles" in request.headers
    roles = tuple(
        role.strip() for role in request.headers.get("X-Roles", "").split(",") if role.strip()
    )
    return LocalIdentityProvider(
        request.headers.get("X-Actor-ID", services.settings.local_default_user_id),
        roles or services.settings.local_default_roles,
        full_access=(
            services.settings.app_auth_mode == "local_full_access"
            and not has_explicit_identity
        ),
    ).current_actor()
