"""Identity provider boundary."""

from typing import Protocol

from app.modules.identity_access.models_ds import Actor


class IdentityProvider(Protocol):
    def current_actor(self) -> Actor: ...
