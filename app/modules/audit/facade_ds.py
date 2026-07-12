"""Audit module boundary backed by the compatible repository facade."""

from app.adapters.database.repositories import SqlAlchemyFormRepository
from app.domain.models import AuditEvent


class AuditFacade:
    def __init__(self, repository: SqlAlchemyFormRepository) -> None:
        self._repository = repository

    def append(self, event: AuditEvent) -> None:
        self._repository.add_audit_event(event)
