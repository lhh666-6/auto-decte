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
