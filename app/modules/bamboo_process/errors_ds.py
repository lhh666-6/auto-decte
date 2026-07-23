"""Expected failures for bamboo workflow operations."""


class BambooProcessError(RuntimeError):
    """Base error for expected bamboo workflow failures."""


class BambooPermissionDenied(BambooProcessError):
    pass


class BambooRecordNotFound(BambooProcessError):
    pass


class StaleBambooRevision(BambooProcessError):
    def __init__(self, expected: int, actual: int) -> None:
        self.expected = expected
        self.actual = actual
        super().__init__(f"stale bamboo revision: expected {expected}, actual {actual}")


class BambooIdempotencyConflict(BambooProcessError):
    """同一幂等键已用于不同请求载荷。"""

    def __init__(self, actor_id: str, idempotency_key: str, operation_type: str) -> None:
        self.actor_id = actor_id
        self.idempotency_key = idempotency_key
        self.operation_type = operation_type
        super().__init__(
            f"idempotency key '{idempotency_key}' already used with a different "
            f"payload for {operation_type} by {actor_id}"
        )
