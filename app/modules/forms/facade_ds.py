"""Forms module boundary backed by the compatible repository facade."""

from app.adapters.database.repositories import SqlAlchemyFormRepository


class FormsFacade:
    def __init__(self, repository: SqlAlchemyFormRepository) -> None:
        self.repository = repository
