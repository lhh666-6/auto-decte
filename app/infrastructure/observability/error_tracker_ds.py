"""In-memory error tracker that records errors with structured context."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class ErrorRecord:
    """A single recorded error with its surrounding context."""

    error_type: str
    message: str
    module: str
    operation: str
    form_id: str | None = None
    task_id: str | None = None
    actor_id: str | None = None
    details: dict[str, Any] | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class LocalErrorTracker:
    """Records application errors with context for later retrieval and reporting.

    Thread-safe for single-writer / multiple-reader usage.  Not safe for
    concurrent writes from multiple threads without external locking.
    """

    def __init__(self) -> None:
        self._errors: list[ErrorRecord] = []

    def record(
        self,
        error: Exception,
        *,
        module: str,
        operation: str,
        form_id: str | None = None,
        task_id: str | None = None,
        actor_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> ErrorRecord:
        """Record an exception with its surrounding context."""
        record = ErrorRecord(
            error_type=type(error).__name__,
            message=str(error),
            module=module,
            operation=operation,
            form_id=form_id,
            task_id=task_id,
            actor_id=actor_id,
            details=details,
        )
        self._errors.append(record)
        return record

    @property
    def all(self) -> list[ErrorRecord]:
        """Return a copy of all recorded errors."""
        return list(self._errors)

    @property
    def count(self) -> int:
        """Return the number of recorded errors."""
        return len(self._errors)

    def clear(self) -> None:
        """Remove all recorded errors."""
        self._errors.clear()

    def by_module(self, module: str) -> list[ErrorRecord]:
        """Return errors filtered by originating module name."""
        return [e for e in self._errors if e.module == module]
