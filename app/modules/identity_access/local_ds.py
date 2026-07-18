"""Single-machine identity provider configured by local settings."""

from app.modules.identity_access.models_ds import Actor, Role


class LocalIdentityProvider:
    def __init__(
        self,
        actor_id: str,
        roles: tuple[str, ...],
        *,
        full_access: bool = False,
    ) -> None:
        self._actor = Actor(
            actor_id,
            frozenset(Role(role) for role in roles),
            local_full_access=full_access,
        )

    def current_actor(self) -> Actor:
        return self._actor
