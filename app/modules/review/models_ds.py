"""Review concurrency value objects and exceptions."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class ReviewDraft:
    form_id: str
    expected_version: int
    values: dict[str, object]
    saved_by: str
    updated_at: datetime


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
class ReviewRuleFailure:
    code: str
    field_key: str
    message: str


class ReviewRuleBlocked(RuntimeError):
    def __init__(self, failures: tuple[ReviewRuleFailure, ...]) -> None:
        super().__init__("Review confirmation is blocked by template rules")
        self.failures = failures


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
