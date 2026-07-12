"""Review concurrency value objects and exceptions."""

from dataclasses import dataclass
from datetime import datetime


class LeaseHeldError(RuntimeError):
    pass


class LeaseOwnershipError(RuntimeError):
    pass


class ReviewVersionConflict(RuntimeError):
    def __init__(self, submitted_version: int, current_version: int) -> None:
        super().__init__(
            f"Submitted version {submitted_version} conflicts with current "
            f"version {current_version}"
        )
        self.submitted_version = submitted_version
        self.current_version = current_version


@dataclass(frozen=True, slots=True)
class ReviewLease:
    form_id: str
    owner_id: str
    lease_token: str
    acquired_at: datetime
    expires_at: datetime
    heartbeat_at: datetime
    forced_release_by: str | None = None
    forced_release_reason: str | None = None
